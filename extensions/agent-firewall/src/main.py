"""
FastAPI Application — Agent Firewall HTTP Entry Point.

This is the main application that wires together all components:
  • Transport adapters (SSE, WebSocket).
  • Session manager.
  • Dual analysis engine (L1 + L2).
  • Audit logger.
  • Dashboard WebSocket hub.

The application exposes:
  /mcp/*          — Proxy endpoints for MCP traffic (POST + SSE).
  /ws/mcp         — WebSocket proxy for MCP traffic.
  /ws/dashboard    — WebSocket for the God Mode Console.
  /api/stats       — Firewall statistics.
  /api/audit       — Recent audit entries.
  /health          — Health check.

Startup sequence:
  1. Load configuration from environment.
  2. Initialize engines (L1 automaton build, L2 client pool).
  3. Start session manager GC.
  4. Start audit logger flush task.
  5. Begin accepting connections.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .audit.logger import AuditLogger
from .config import FirewallConfig
from .dashboard.ws_handler import DashboardHub
from .engine.semantic_analyzer import MockClassifier, SemanticAnalyzer
from .engine.static_analyzer import StaticAnalyzer
from .models import AuditEntry, DashboardEvent
from .proxy.session_manager import SessionManager
from .proxy.sse_adapter import SseAdapter, WebSocketAdapter

logger = logging.getLogger("agent_firewall")


# ────────────────────────────────────────────────────────────────────
# Application State (singleton per worker)
# ────────────────────────────────────────────────────────────────────


class AppState:
    """Container for all shared application state."""

    def __init__(self, config: FirewallConfig) -> None:
        self.config = config
        self.static_analyzer = StaticAnalyzer(config.blocked_commands)
        self.semantic_analyzer = SemanticAnalyzer(
            classifier=MockClassifier(),  # Default to mock; swap for production
            config=config,
        )
        self.session_manager = SessionManager(config)
        self.audit_logger = AuditLogger(config.audit_log_path)
        self.dashboard_hub = DashboardHub()
        self.sse_adapter = SseAdapter(
            upstream_base_url=f"http://{config.upstream_host}:{config.upstream_port}",
            session_manager=self.session_manager,
            static_analyzer=self.static_analyzer,
            semantic_analyzer=self.semantic_analyzer,
            emit_dashboard_event=self._emit_dashboard,
            emit_audit_entry=self._emit_audit,
        )
        self.ws_adapter = WebSocketAdapter(
            upstream_ws_url=f"ws://{config.upstream_host}:{config.upstream_port}/ws",
            session_manager=self.session_manager,
            static_analyzer=self.static_analyzer,
            semantic_analyzer=self.semantic_analyzer,
            emit_dashboard_event=self._emit_dashboard,
            emit_audit_entry=self._emit_audit,
        )
        self._start_time = time.time()

    async def _emit_dashboard(self, event: DashboardEvent) -> None:
        await self.dashboard_hub.broadcast(event)

    async def _emit_audit(self, entry: AuditEntry) -> None:
        await self.audit_logger.log(entry)

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self._start_time


# ────────────────────────────────────────────────────────────────────
# Lifespan
# ────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifecycle management."""
    config = FirewallConfig()
    state = AppState(config)
    app.state.firewall = state

    # Start background services
    await state.session_manager.start()
    await state.audit_logger.start()

    logger.info(
        "🛡️  Agent Firewall started on %s:%d → upstream %s:%d",
        config.listen_host,
        config.listen_port,
        config.upstream_host,
        config.upstream_port,
    )

    yield

    # Graceful shutdown
    await state.audit_logger.stop()
    await state.session_manager.stop()
    await state.sse_adapter.close()
    logger.info("Agent Firewall shut down gracefully")


# ────────────────────────────────────────────────────────────────────
# FastAPI Application
# ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="OpenClaw Agent Firewall",
    description="Zero-Trust Agent Communication Security Gateway",
    version="2026.2.16",
    lifespan=lifespan,
)

# CORS for dashboard frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _state(request: Request | None = None) -> AppState:
    """Extract AppState from the ASGI app."""
    from fastapi import Request as _Req

    if request is not None:
        return request.app.state.firewall  # type: ignore[no-any-return]
    raise RuntimeError("No request context")


# ── Health ────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "agent-firewall"}


# ── Stats ─────────────────────────────────────────────────────────


@app.get("/api/stats")
async def stats(request: Request) -> JSONResponse:
    s = _state(request)
    return JSONResponse(
        {
            "uptime_seconds": round(s.uptime_seconds, 1),
            "active_sessions": s.session_manager.active_count,
            "dashboard_clients": s.dashboard_hub.client_count,
            "audit": s.audit_logger.stats,
        }
    )


# ── MCP Proxy (HTTP POST) ────────────────────────────────────────


@app.post("/mcp/{path:path}")
async def mcp_post(request: Request) -> JSONResponse:
    s = _state(request)
    response = await s.sse_adapter.handle_post(request)
    return response  # type: ignore[return-value]


@app.post("/mcp")
async def mcp_post_root(request: Request) -> JSONResponse:
    s = _state(request)
    response = await s.sse_adapter.handle_post(request)
    return response  # type: ignore[return-value]


# ── MCP Proxy (SSE) ──────────────────────────────────────────────


@app.get("/mcp/sse")
async def mcp_sse(request: Request):  # noqa: ANN201
    s = _state(request)
    return await s.sse_adapter.handle_sse(request)


# ── MCP Proxy (WebSocket) ────────────────────────────────────────


@app.websocket("/ws/mcp")
async def mcp_websocket(ws: WebSocket) -> None:
    s = ws.app.state.firewall
    await s.ws_adapter.handle_websocket(ws)


# ── Dashboard WebSocket ──────────────────────────────────────────


@app.websocket("/ws/dashboard")
async def dashboard_websocket(ws: WebSocket) -> None:
    s = ws.app.state.firewall
    await s.dashboard_hub.handle_client(ws)


# ── Logging config ───────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
