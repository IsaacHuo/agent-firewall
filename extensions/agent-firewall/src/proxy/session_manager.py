"""
Session Manager — Stateful Context Reconstruction for Stateless Protocols.

MCP traffic over SSE/WebSocket is inherently request-response, but security
analysis requires *conversation context* — knowing what the agent said 5 turns
ago is critical for detecting multi-hop injection chains.

This module reconstructs full session state by:
  1. Binding each inbound request to an Agent identity (via headers, auth tokens,
     or MCP `clientInfo` from the `initialize` handshake).
  2. Maintaining a per-session ring buffer of recent messages.
  3. Correlating JSON-RPC request IDs to their responses.
  4. Garbage-collecting expired sessions via a background sweep task.

Memory model:
  • Each session holds at most `ring_buffer_size` messages (~64 by default).
  • Session TTL defaults to 1 hour; expired sessions are swept every 60s.
  • Total memory ≈ num_active_sessions × buffer_size × avg_message_size.
    For 1000 sessions × 64 messages × 1KB ≈ 64MB — well within bounds.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from ..config import FirewallConfig
from ..models import SessionContext

logger = logging.getLogger("agent_firewall.session")


class SessionManager:
    """
    In-memory session store with TTL-based garbage collection.

    Thread-safety: All access is from the asyncio event loop (single-threaded).
    No locks needed — we use asyncio.Lock only for the GC sweep to prevent
    concurrent modification during iteration.
    """

    def __init__(self, config: FirewallConfig | None = None) -> None:
        cfg = config or FirewallConfig()
        self._sessions: dict[str, SessionContext] = {}
        self._buffer_size = cfg.session_ring_buffer_size
        self._ttl = cfg.session_ttl_seconds
        self._gc_lock = asyncio.Lock()
        self._gc_task: Optional[asyncio.Task[None]] = None

    async def start(self) -> None:
        """Start the background GC sweep task."""
        self._gc_task = asyncio.create_task(self._gc_loop())
        logger.info(
            "Session manager started (buffer=%d, ttl=%ds)",
            self._buffer_size,
            self._ttl,
        )

    async def stop(self) -> None:
        """Cancel the GC task and clear all sessions."""
        if self._gc_task is not None:
            self._gc_task.cancel()
            try:
                await self._gc_task
            except asyncio.CancelledError:
                pass
        self._sessions.clear()
        logger.info("Session manager stopped, %d sessions cleared", len(self._sessions))

    def get_or_create(
        self,
        session_id: str,
        agent_id: str = "",
    ) -> SessionContext:
        """
        Retrieve an existing session or create a new one.

        The session_id is typically derived from:
          • stdio mode: PID of the child process.
          • SSE mode: A unique request header (X-Session-ID) or auth token hash.
          • WebSocket mode: The WebSocket connection ID.

        Args:
            session_id: Unique session identifier.
            agent_id: Human-readable agent name (from MCP clientInfo).

        Returns:
            The SessionContext for this session.
        """
        if session_id in self._sessions:
            session = self._sessions[session_id]
            session.last_active = time.time()
            return session

        session = SessionContext(
            session_id=session_id,
            agent_id=agent_id,
            max_messages=self._buffer_size,
        )
        self._sessions[session_id] = session
        logger.debug("Created new session: %s (agent=%s)", session_id[:8], agent_id)
        return session

    def get(self, session_id: str) -> Optional[SessionContext]:
        """Look up a session without creating it."""
        return self._sessions.get(session_id)

    @property
    def active_count(self) -> int:
        return len(self._sessions)

    async def _gc_loop(self) -> None:
        """
        Periodic garbage collection of expired sessions.

        Runs every 60 seconds. Uses an async lock to prevent
        concurrent modification during the sweep.
        """
        while True:
            try:
                await asyncio.sleep(60)
                async with self._gc_lock:
                    now = time.time()
                    expired = [
                        sid
                        for sid, session in self._sessions.items()
                        if (now - session.last_active) > self._ttl
                    ]
                    for sid in expired:
                        del self._sessions[sid]
                    if expired:
                        logger.info("GC swept %d expired sessions", len(expired))
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.error("Session GC error: %s", exc)
