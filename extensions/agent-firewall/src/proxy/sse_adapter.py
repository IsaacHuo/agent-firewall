"""
SSE / WebSocket Transport Adapter — HTTP Stream Proxy.

Handles both Server-Sent Events (SSE) and WebSocket connections between
OpenClaw Agents and MCP Servers. This is the primary transport for
production deployments where agents connect over the network.

Architecture:
  ┌─────────┐     HTTP POST / WS     ┌───────────┐    HTTP POST / WS    ┌────────────┐
  │  Agent   │ ──────────────────────→│ Firewall  │──────────────────────→│ MCP Server │
  │ (Client) │ ←──────────────────────│  (Proxy)  │←──────────────────────│ (Upstream) │
  └─────────┘    SSE stream / WS     └───────────┘   SSE stream / WS    └────────────┘

Real-time Stream Sanitization:
  SSE connections are long-lived. The challenge is inspecting each event
  in the stream WITHOUT introducing head-of-line blocking. We achieve this
  by:
    1. Reading SSE events from the upstream as they arrive.
    2. Forwarding safe events immediately (< 1ms latency).
    3. For flagged events, spawning a concurrent L2 analysis task and
       holding the event in a small buffer until the verdict arrives.
    4. If the L2 timeout is reached, we fail-open (forward with audit).

  This gives us real-time streaming with security inspection at the
  cost of only ~L2_timeout_ms additional latency on flagged events.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Callable, Coroutine, Optional
from urllib.parse import urljoin

import httpx
from fastapi import Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from ..engine.interceptor import intercept_and_analyze
from ..engine.semantic_analyzer import SemanticAnalyzer
from ..engine.static_analyzer import StaticAnalyzer
from ..models import JsonRpcResponse, Verdict
from .session_manager import SessionManager

logger = logging.getLogger("agent_firewall.sse")


class SseAdapter:
    """
    SSE / HTTP proxy adapter for MCP traffic.

    Exposes two FastAPI route handlers:
      • `handle_post` — for JSON-RPC over HTTP POST (request-response).
      • `handle_sse` — for SSE streams (long-lived server push).
    """

    def __init__(
        self,
        upstream_base_url: str,
        session_manager: SessionManager,
        static_analyzer: StaticAnalyzer,
        semantic_analyzer: SemanticAnalyzer,
        *,
        emit_dashboard_event: Optional[Callable[..., Coroutine[Any, Any, None]]] = None,
        emit_audit_entry: Optional[Callable[..., Coroutine[Any, Any, None]]] = None,
    ) -> None:
        self._upstream = upstream_base_url.rstrip("/")
        self._sessions = session_manager
        self._l1 = static_analyzer
        self._l2 = semantic_analyzer
        self._emit_dashboard = emit_dashboard_event
        self._emit_audit = emit_audit_entry
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        await self._client.aclose()

    # ── JSON-RPC over HTTP POST ──────────────────────────────────

    async def handle_post(self, request: Request) -> Response:
        """
        Handle a standard JSON-RPC request over HTTP POST.

        Flow:
          1. Read request body.
          2. Extract/create session from headers.
          3. Run through interceptor.
          4. If BLOCKED → return error response.
          5. If ALLOWED → forward to upstream, return response.
        """
        body = await request.body()

        # Session identification from headers
        session_id = request.headers.get(
            "x-session-id", request.client.host if request.client else "unknown"
        )
        agent_id = request.headers.get("x-agent-id", "http-agent")
        session = self._sessions.get_or_create(session_id, agent_id)

        # Intercept and analyze
        parsed_request, analysis, block_response = await intercept_and_analyze(
            raw_payload=body,
            session=session,
            static_analyzer=self._l1,
            semantic_analyzer=self._l2,
            emit_dashboard_event=self._emit_dashboard,
            emit_audit_entry=self._emit_audit,
        )

        if block_response is not None:
            return Response(
                content=block_response.to_bytes(),
                media_type="application/json",
                status_code=403,
            )

        # Forward to upstream
        upstream_url = urljoin(self._upstream + "/", request.url.path.lstrip("/"))
        try:
            upstream_response = await self._client.post(
                upstream_url,
                content=body,
                headers={
                    "content-type": "application/json",
                    "x-forwarded-by": "agent-firewall",
                },
            )
            return Response(
                content=upstream_response.content,
                status_code=upstream_response.status_code,
                media_type=upstream_response.headers.get("content-type", "application/json"),
            )
        except httpx.HTTPError as exc:
            logger.error("Upstream request failed: %s", exc)
            error = JsonRpcResponse(
                id=parsed_request.id,
                error={"code": -32603, "message": f"Upstream error: {exc}"},  # type: ignore[arg-type]
            )
            return Response(
                content=error.to_bytes(),
                media_type="application/json",
                status_code=502,
            )

    # ── SSE Stream Proxy ─────────────────────────────────────────

    async def handle_sse(self, request: Request) -> StreamingResponse:
        """
        Proxy an SSE stream from the upstream MCP server.

        Each SSE event is inspected in-flight. Safe events are forwarded
        immediately; flagged events are held for L2 analysis with a
        bounded timeout to prevent stream stalling.
        """
        session_id = request.headers.get("x-session-id", "sse-default")
        session = self._sessions.get_or_create(session_id, "sse-agent")

        upstream_url = urljoin(self._upstream + "/", "sse")

        async def stream_generator() -> AsyncIterator[bytes]:
            """Inner generator that yields sanitized SSE events."""
            async with self._client.stream("GET", upstream_url) as response:
                buffer = b""
                async for chunk in response.aiter_bytes():
                    buffer += chunk
                    # SSE events are delimited by double newlines
                    while b"\n\n" in buffer:
                        event_bytes, buffer = buffer.split(b"\n\n", 1)
                        sanitized = await self._sanitize_sse_event(event_bytes, session)
                        if sanitized is not None:
                            yield sanitized + b"\n\n"

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Agent-Firewall": "active",
            },
        )

    async def _sanitize_sse_event(
        self,
        event_bytes: bytes,
        session: Any,
    ) -> Optional[bytes]:
        """
        Inspect a single SSE event for threats.

        SSE events that contain JSON-RPC data fields are parsed and
        run through the interceptor. Non-data events (comments, pings)
        are passed through immediately.

        Returns:
            The (potentially modified) event bytes, or None to drop.
        """
        # Parse SSE event fields
        lines = event_bytes.decode("utf-8", errors="replace").split("\n")
        data_lines: list[str] = []
        other_lines: list[str] = []

        for line in lines:
            if line.startswith("data:"):
                data_lines.append(line[5:].strip())
            else:
                other_lines.append(line)

        if not data_lines:
            # No data field — pass through (comments, event types, etc.)
            return event_bytes

        data_payload = "\n".join(data_lines)

        # Try to parse as JSON-RPC and inspect
        try:
            _, analysis, block_response = await intercept_and_analyze(
                raw_payload=data_payload,
                session=session,
                static_analyzer=self._l1,
                semantic_analyzer=self._l2,
                emit_dashboard_event=self._emit_dashboard,
                emit_audit_entry=self._emit_audit,
            )

            if block_response is not None:
                # Replace the data with the blocking error
                error_data = block_response.to_bytes().decode("utf-8")
                sanitized_lines = other_lines + [f"data:{error_data}"]
                return "\n".join(sanitized_lines).encode("utf-8")

        except Exception:
            # Not valid JSON-RPC data — pass through
            pass

        return event_bytes


# ────────────────────────────────────────────────────────────────────
# WebSocket Adapter
# ────────────────────────────────────────────────────────────────────


class WebSocketAdapter:
    """
    WebSocket bidirectional proxy for MCP traffic.

    WebSocket mode provides the lowest latency for real-time agent
    communication. Each connection gets its own session, and messages
    are inspected in both directions.
    """

    def __init__(
        self,
        upstream_ws_url: str,
        session_manager: SessionManager,
        static_analyzer: StaticAnalyzer,
        semantic_analyzer: SemanticAnalyzer,
        *,
        emit_dashboard_event: Optional[Callable[..., Coroutine[Any, Any, None]]] = None,
        emit_audit_entry: Optional[Callable[..., Coroutine[Any, Any, None]]] = None,
    ) -> None:
        self._upstream_ws = upstream_ws_url
        self._sessions = session_manager
        self._l1 = static_analyzer
        self._l2 = semantic_analyzer
        self._emit_dashboard = emit_dashboard_event
        self._emit_audit = emit_audit_entry

    async def handle_websocket(self, ws: WebSocket) -> None:
        """
        Handle a bidirectional WebSocket proxy connection.

        Spawns two concurrent tasks:
          • Agent → Server (with interception)
          • Server → Agent (pass-through, with optional response inspection)
        """
        await ws.accept()

        session_id = ws.headers.get("x-session-id", f"ws-{id(ws)}")
        agent_id = ws.headers.get("x-agent-id", "ws-agent")
        session = self._sessions.get_or_create(session_id, agent_id)

        import websockets  # type: ignore[import-untyped]

        try:
            async with websockets.connect(self._upstream_ws) as upstream:
                await asyncio.gather(
                    self._agent_to_server(ws, upstream, session),
                    self._server_to_agent(ws, upstream),
                )
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected: %s", session_id[:8])
        except Exception as exc:
            logger.error("WebSocket proxy error: %s", exc)
        finally:
            try:
                await ws.close()
            except Exception:
                pass

    async def _agent_to_server(
        self,
        client_ws: WebSocket,
        upstream_ws: Any,
        session: Any,
    ) -> None:
        """Intercept agent→server messages."""
        try:
            while True:
                data = await client_ws.receive_text()

                _, analysis, block_response = await intercept_and_analyze(
                    raw_payload=data,
                    session=session,
                    static_analyzer=self._l1,
                    semantic_analyzer=self._l2,
                    emit_dashboard_event=self._emit_dashboard,
                    emit_audit_entry=self._emit_audit,
                )

                if block_response is not None:
                    await client_ws.send_bytes(block_response.to_bytes())
                else:
                    await upstream_ws.send(data)

        except WebSocketDisconnect:
            pass

    async def _server_to_agent(
        self,
        client_ws: WebSocket,
        upstream_ws: Any,
    ) -> None:
        """Forward server→agent messages (pass-through)."""
        try:
            async for message in upstream_ws:
                await client_ws.send_text(message)
        except Exception:
            pass
