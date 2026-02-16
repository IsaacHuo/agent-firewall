"""
Dashboard WebSocket Handler — Real-Time Event Broadcasting.

Pushes firewall events to all connected God Mode Console clients via
WebSocket. This is the server-side counterpart of the Vue 3 dashboard.

Architecture:
  • A single broadcast hub maintains the set of connected clients.
  • Events are pushed from the interceptor via `emit_dashboard_event()`.
  • Each client receives events as JSON, filtered by their subscription.
  • Backpressure: if a client falls behind, events are dropped (not queued
    indefinitely) to prevent memory exhaustion from slow consumers.

Wire protocol (server → client):
  {
    "event_type": "request" | "alert" | "verdict" | "stats",
    "timestamp": 1700000000.0,
    "session_id": "abc123",
    "method": "tools/call",
    "payload_preview": "{...}",
    "analysis": { ... },
    "is_alert": true
  }

Wire protocol (client → server):
  {
    "action": "block" | "allow",     // Human-in-the-loop verdict
    "request_id": "abc123"           // The escalated request to act on
  }
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from ..models import DashboardEvent, Verdict

logger = logging.getLogger("agent_firewall.dashboard")

# Maximum events buffered per slow client before we start dropping
_CLIENT_BUFFER_SIZE = 256


class DashboardHub:
    """
    Central WebSocket broadcast hub for the God Mode Console.

    Thread-safety: all operations are confined to the asyncio event loop.
    """

    def __init__(self) -> None:
        self._clients: dict[int, asyncio.Queue[bytes]] = {}
        # Pending escalations waiting for human verdict
        self._pending_escalations: dict[str, asyncio.Future[Verdict]] = {}

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def connect(self, ws: WebSocket) -> int:
        """Register a new dashboard client."""
        await ws.accept()
        client_id = id(ws)
        self._clients[client_id] = asyncio.Queue(maxsize=_CLIENT_BUFFER_SIZE)
        logger.info("Dashboard client connected: %d (total: %d)", client_id, len(self._clients))
        return client_id

    def disconnect(self, client_id: int) -> None:
        """Unregister a dashboard client."""
        self._clients.pop(client_id, None)
        logger.info("Dashboard client disconnected: %d (total: %d)", client_id, len(self._clients))

    async def broadcast(self, event: DashboardEvent) -> None:
        """
        Push an event to all connected clients.

        Uses non-blocking put to avoid backpressure from slow clients.
        Events are dropped for clients whose buffers are full.
        """
        data = event.to_bytes()
        dropped = 0
        for client_id, queue in self._clients.items():
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                dropped += 1
                # Drop oldest event to make room
                try:
                    queue.get_nowait()
                    queue.put_nowait(data)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

        if dropped > 0:
            logger.warning("Dropped events for %d slow dashboard clients", dropped)

    async def handle_client(self, ws: WebSocket) -> None:
        """
        Handle a single dashboard WebSocket client lifecycle.

        Runs two concurrent tasks:
          • Sender: pulls from the client's queue and pushes to WS.
          • Receiver: listens for human-in-the-loop actions (block/allow).
        """
        client_id = await self.connect(ws)
        queue = self._clients[client_id]

        try:
            await asyncio.gather(
                self._client_sender(ws, queue),
                self._client_receiver(ws),
            )
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.error("Dashboard client error: %s", exc)
        finally:
            self.disconnect(client_id)

    async def _client_sender(self, ws: WebSocket, queue: asyncio.Queue[bytes]) -> None:
        """Send queued events to the client."""
        while True:
            data = await queue.get()
            try:
                await ws.send_bytes(data)
            except Exception:
                break

    async def _client_receiver(self, ws: WebSocket) -> None:
        """
        Receive human-in-the-loop actions from the dashboard.

        Supports:
          • {"action": "block", "request_id": "..."} — block an escalated request.
          • {"action": "allow", "request_id": "..."} — allow an escalated request.
        """
        import orjson

        while True:
            try:
                raw = await ws.receive_text()
                msg = orjson.loads(raw)
                action = msg.get("action")
                request_id = msg.get("request_id")

                if action and request_id and request_id in self._pending_escalations:
                    verdict = Verdict.BLOCK if action == "block" else Verdict.ALLOW
                    future = self._pending_escalations.pop(request_id)
                    if not future.done():
                        future.set_result(verdict)
                    logger.info(
                        "Human verdict for %s: %s",
                        request_id,
                        verdict.value,
                    )
            except WebSocketDisconnect:
                raise
            except Exception as exc:
                logger.warning("Invalid dashboard action: %s", exc)

    async def request_human_verdict(self, request_id: str, timeout: float = 30.0) -> Verdict:
        """
        Request a human-in-the-loop decision for an escalated request.

        Blocks until a dashboard operator responds or timeout is reached.
        On timeout, defaults to BLOCK (fail-safe).

        Args:
            request_id: The unique ID of the escalated request.
            timeout: Maximum seconds to wait for a human response.

        Returns:
            The human verdict, or BLOCK on timeout.
        """
        future: asyncio.Future[Verdict] = asyncio.get_event_loop().create_future()
        self._pending_escalations[request_id] = future

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_escalations.pop(request_id, None)
            logger.warning("Human verdict timeout for %s — defaulting to BLOCK", request_id)
            return Verdict.BLOCK
