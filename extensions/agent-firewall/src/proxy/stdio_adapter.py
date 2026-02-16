"""
stdio Transport Adapter — Subprocess Pipe Interception.

In stdio mode, the MCP Server is launched as a child process with its
stdin/stdout connected to the agent. The firewall sits *between* them:

    Agent  ──stdin──→  [Firewall]  ──stdin──→  MCP Server (child)
    Agent  ←─stdout──  [Firewall]  ←─stdout──  MCP Server (child)

This adapter:
  1. Spawns the MCP server as an asyncio subprocess.
  2. Reads newline-delimited JSON-RPC from the agent's stdin.
  3. Passes each message through the interceptor pipeline.
  4. Forwards allowed messages to the child's stdin.
  5. Reads responses from the child's stdout and forwards back.

Stream Sanitization:
  The key challenge is that stdio is a continuous byte stream — there's
  no framing beyond newlines. We use an incremental line reader that
  buffers partial lines without blocking, ensuring real-time throughput
  even during slow LLM analysis (L2 runs concurrently via asyncio.create_task).
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any, Callable, Coroutine, Optional

from ..engine.interceptor import intercept_and_analyze
from ..engine.semantic_analyzer import SemanticAnalyzer
from ..engine.static_analyzer import StaticAnalyzer
from ..models import JsonRpcResponse, Verdict
from .session_manager import SessionManager

logger = logging.getLogger("agent_firewall.stdio")

# Maximum line size before we forcibly flush (defense against memory exhaustion)
_MAX_LINE_BYTES = 4 * 1024 * 1024  # 4MB


class StdioAdapter:
    """
    Non-invasive stdio MITM proxy for MCP servers.

    Usage:
        adapter = StdioAdapter(
            server_command=["node", "mcp-server/index.js"],
            session_manager=session_mgr,
            static_analyzer=l1,
            semantic_analyzer=l2,
        )
        await adapter.run()
    """

    def __init__(
        self,
        server_command: list[str],
        session_manager: SessionManager,
        static_analyzer: StaticAnalyzer,
        semantic_analyzer: SemanticAnalyzer,
        *,
        emit_dashboard_event: Optional[Callable[..., Coroutine[Any, Any, None]]] = None,
        emit_audit_entry: Optional[Callable[..., Coroutine[Any, Any, None]]] = None,
    ) -> None:
        self._server_cmd = server_command
        self._sessions = session_manager
        self._l1 = static_analyzer
        self._l2 = semantic_analyzer
        self._emit_dashboard = emit_dashboard_event
        self._emit_audit = emit_audit_entry
        self._process: Optional[asyncio.subprocess.Process] = None

    async def run(self) -> None:
        """
        Main event loop: spawn child process and pipe traffic bidirectionally.

        This method blocks until either the child process exits or the
        agent closes stdin. Both directions run as concurrent tasks.
        """
        logger.info("Starting stdio adapter: %s", " ".join(self._server_cmd))

        self._process = await asyncio.create_subprocess_exec(
            *self._server_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        assert self._process.stdin is not None
        assert self._process.stdout is not None

        # Create a session for this stdio connection
        session = self._sessions.get_or_create(
            session_id=f"stdio-{self._process.pid}",
            agent_id="stdio-agent",
        )

        try:
            # Run bidirectional pipes concurrently
            await asyncio.gather(
                self._pipe_agent_to_server(session),
                self._pipe_server_to_agent(),
            )
        except asyncio.CancelledError:
            logger.info("stdio adapter cancelled, terminating child process")
        finally:
            if self._process.returncode is None:
                self._process.terminate()
                await self._process.wait()

    async def _pipe_agent_to_server(self, session: Any) -> None:
        """
        Read from agent stdin → intercept → forward to server stdin.

        Each line is a complete JSON-RPC message. We intercept each one
        and only forward if the verdict is ALLOW.
        """
        assert self._process is not None
        assert self._process.stdin is not None

        reader = asyncio.StreamReader()
        transport, _ = await asyncio.get_event_loop().connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(reader),
            sys.stdin.buffer,
        )

        try:
            while True:
                line = await reader.readline()
                if not line:
                    break  # Agent closed stdin

                if len(line) > _MAX_LINE_BYTES:
                    logger.warning("Oversized message dropped (%d bytes)", len(line))
                    continue

                # Run through the interceptor
                request, analysis, block_response = await intercept_and_analyze(
                    raw_payload=line,
                    session=session,
                    static_analyzer=self._l1,
                    semantic_analyzer=self._l2,
                    emit_dashboard_event=self._emit_dashboard,
                    emit_audit_entry=self._emit_audit,
                )

                if block_response is not None:
                    # Send the blocking error back to the agent
                    error_line = block_response.to_bytes() + b"\n"
                    sys.stdout.buffer.write(error_line)
                    sys.stdout.buffer.flush()
                else:
                    # Forward the original (unmodified) message to the server
                    self._process.stdin.write(line)
                    await self._process.stdin.drain()

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Agent→Server pipe error: %s", exc, exc_info=True)
        finally:
            transport.close()

    async def _pipe_server_to_agent(self) -> None:
        """
        Read from server stdout → forward to agent stdout.

        Response traffic is forwarded without interception by default.
        (Response sanitization can be added as a future enhancement.)
        """
        assert self._process is not None
        assert self._process.stdout is not None

        try:
            while True:
                line = await self._process.stdout.readline()
                if not line:
                    break  # Server closed stdout
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Server→Agent pipe error: %s", exc, exc_info=True)
