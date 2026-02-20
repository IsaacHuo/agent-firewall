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
import os
import time
from contextlib import asynccontextmanager
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, AsyncIterator

# Load .env file before importing config
from dotenv import load_dotenv

_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .audit.logger import AuditLogger
from .config import FirewallConfig
from .dashboard.ws_handler import DashboardHub
from .engine.semantic_analyzer import LlmClassifier, MockClassifier, SemanticAnalyzer
from .engine.static_analyzer import StaticAnalyzer
from .models import AuditEntry, DashboardEvent
from .proxy.session_manager import SessionManager
from .proxy.sse_adapter import SseAdapter, WebSocketAdapter
from .proxy.openai_adapter import OpenAIAdapter

logger = logging.getLogger("agent_firewall")


# ────────────────────────────────────────────────────────────────────
# Application State (singleton per worker)
# ────────────────────────────────────────────────────────────────────


class AppState:
    """Container for all shared application state."""

    def __init__(self, config: FirewallConfig) -> None:
        self.config = config
        self.static_analyzer = StaticAnalyzer(config.blocked_commands)
        # Use LlmClassifier if L2 is enabled, else Mock
        self.semantic_analyzer = SemanticAnalyzer(
            classifier=LlmClassifier(config) if config.l2_enabled else MockClassifier(),
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

        # Initialize OpenAI proxy using L2 configuration as upstream hint
        l2_base = config.l2_model_endpoint
        if "/chat/completions" in l2_base:
            openai_upstream = l2_base.replace("/chat/completions", "")
        else:
            openai_upstream = "https://openrouter.ai/api/v1"

        self.openai_adapter = OpenAIAdapter(
            upstream_base_url=openai_upstream,
            static_analyzer=self.static_analyzer,
            semantic_analyzer=self.semantic_analyzer,
            api_key=config.l2_api_key,
        )

        self._start_time = time.time()

    async def reload_config(self, updates: dict[str, Any]) -> None:
        """Update the configuration and re-initialize downstream services."""
        # Convert frozen dataclass to dict, update with the partial changes, then re-create
        new_config_dict = asdict(self.config)
        new_config_dict.update(updates)

        # Coerce types if necessary (e.g. list from JSON to frozenset)
        if "blocked_commands" in new_config_dict and isinstance(
            new_config_dict["blocked_commands"], list
        ):
            new_config_dict["blocked_commands"] = frozenset(new_config_dict["blocked_commands"])

        self.config = FirewallConfig(**new_config_dict)

        # Re-initialize only the parts that depend on the updated config
        # (For L1, we handle separately through the /rules endpoints if needed,
        # but here we synchronize the whole config's blocked_commands as well).
        if "blocked_commands" in updates:
            self.static_analyzer = StaticAnalyzer(self.config.blocked_commands)

        if "l2_enabled" in updates or "l2_api_key" in updates or "l2_model" in updates:
            # Shutdown old client if it's LlmClassifier
            await self.semantic_analyzer.close()

            self.semantic_analyzer = SemanticAnalyzer(
                classifier=LlmClassifier(self.config)
                if self.config.l2_enabled
                else MockClassifier(),
                config=self.config,
            )

        # Update adapters with new analyzer refs
        self.sse_adapter.static_analyzer = self.static_analyzer
        self.sse_adapter.semantic_analyzer = self.semantic_analyzer
        self.ws_adapter.static_analyzer = self.static_analyzer
        self.ws_adapter.semantic_analyzer = self.semantic_analyzer

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
    await state.semantic_analyzer.close()

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


# ── Configuration ───────────────────────────────────────────────


@app.get("/api/config")
async def get_config(request: Request) -> dict[str, Any]:
    s = _state(request)
    c = s.config
    # Transform flat config to nested structure for frontend
    return {
        "network": {
            "listen_host": c.listen_host,
            "listen_port": c.listen_port,
            "upstream_host": c.upstream_host,
            "upstream_port": c.upstream_port,
            "transport_mode": c.transport_mode,
        },
        "engine": {
            "l1_enabled": c.l1_enabled,
            "l2_enabled": c.l2_enabled,
            "l2_model_endpoint": c.l2_model_endpoint,
            "l2_api_key": c.l2_api_key,
            "l2_model": c.l2_model,
            "l2_timeout_seconds": c.l2_timeout_seconds,
        },
        "session": {
            # These might be missing in config.py, check source
            "ring_buffer_size": getattr(c, "session_ring_buffer_size", 64),
            "ttl_seconds": getattr(c, "session_ttl_seconds", 3600),
        },
        "rate_limit": {
            "requests_per_sec": getattr(c, "rate_limit_requests_per_sec", 100),
            "burst": getattr(c, "rate_limit_burst", 200),
        },
        "audit_log_path": c.audit_log_path,
        "blocked_commands": sorted(list(c.blocked_commands)),
    }


@app.patch("/api/config")
async def patch_config(request: Request) -> dict[str, Any]:
    s = _state(request)
    updates = await request.json()

    # Flatten updates if nested
    flat_updates = {}

    # Copy top-level fields
    for k, v in updates.items():
        if not isinstance(v, dict):
            flat_updates[k] = v

    if "network" in updates:
        flat_updates.update(updates["network"])
    if "engine" in updates:
        flat_updates.update(updates["engine"])
    if "session" in updates:
        # Prefix session fields
        for k, v in updates["session"].items():
            if k == "ring_buffer_size":
                flat_updates["session_ring_buffer_size"] = v
            elif k == "ttl_seconds":
                flat_updates["session_ttl_seconds"] = v
            else:
                flat_updates[k] = v  # fallback

    if "rate_limit" in updates:
        for k, v in updates["rate_limit"].items():
            if k == "requests_per_sec":
                flat_updates["rate_limit_requests_per_sec"] = v
            elif k == "burst":
                flat_updates["rate_limit_burst"] = v
            else:
                flat_updates[k] = v

    await s.reload_config(flat_updates)

    # Return NEW config in nested format (call get_config logic conceptually)
    # Since get_config reads s.config, and we just updated it, calling get_config logic is best.
    # But get_config extracts from request. Let's just manually re-serialize or return ok.
    # The frontend expects the new config back.

    # Re-use the response structure from get_config
    c = s.config
    return {
        "network": {
            "listen_host": c.listen_host,
            "listen_port": c.listen_port,
            "upstream_host": c.upstream_host,
            "upstream_port": c.upstream_port,
            "transport_mode": c.transport_mode,
        },
        "engine": {
            "l1_enabled": c.l1_enabled,
            "l2_enabled": c.l2_enabled,
            "l2_model_endpoint": c.l2_model_endpoint,
            "l2_api_key": c.l2_api_key,
            "l2_model": c.l2_model,
            "l2_timeout_seconds": c.l2_timeout_seconds,
        },
        "session": {
            "ring_buffer_size": getattr(c, "session_ring_buffer_size", 64),
            "ttl_seconds": getattr(c, "session_ttl_seconds", 3600),
        },
        "rate_limit": {
            "requests_per_sec": getattr(c, "rate_limit_requests_per_sec", 100),
            "burst": getattr(c, "rate_limit_burst", 200),
        },
        "audit_log_path": c.audit_log_path,
        "blocked_commands": sorted(list(c.blocked_commands)),
    }


# ── Rules Management ─────────────────────────────────────────────

# In-memory storage for pattern rules (would persist to DB or file in production)
_pattern_rules: dict[str, dict[str, Any]] = {}
_method_rules: list[dict[str, Any]] = []
_agent_rules: list[dict[str, Any]] = []
_default_action: str = "ALLOW"


def _init_default_rules(blocked_commands: frozenset[str]) -> None:
    """Initialize pattern rules from blocked_commands config."""
    global _pattern_rules
    if not _pattern_rules:
        for i, cmd in enumerate(sorted(blocked_commands)):
            rule_id = f"default-{i+1}"
            _pattern_rules[rule_id] = {
                "id": rule_id,
                "name": f"Block: {cmd}",
                "pattern": cmd,
                "type": "literal",
                "action": "BLOCK",
                "threat_level": "HIGH",
                "enabled": True,
                "description": f"Default blocked pattern: {cmd}",
                "created_at": time.time(),
                "updated_at": time.time(),
            }


@app.get("/api/rules")
async def get_rules(request: Request) -> dict[str, Any]:
    """Get all rules in the format expected by frontend."""
    s = _state(request)
    _init_default_rules(s.config.blocked_commands)

    return {
        "pattern_rules": list(_pattern_rules.values()),
        "method_rules": _method_rules,
        "agent_rules": _agent_rules,
        "default_action": _default_action,
    }


@app.post("/api/rules/patterns")
async def create_pattern_rule(request: Request) -> dict[str, Any]:
    """Create a new pattern rule."""
    s = _state(request)
    data = await request.json()

    rule_id = data.get("id") or f"rule-{int(time.time() * 1000)}"
    now = time.time()

    rule = {
        "id": rule_id,
        "name": data.get("name", "Unnamed Rule"),
        "pattern": data.get("pattern", ""),
        "type": data.get("type", "literal"),
        "action": data.get("action", "BLOCK"),
        "threat_level": data.get("threat_level", "HIGH"),
        "enabled": data.get("enabled", True),
        "description": data.get("description", ""),
        "created_at": data.get("created_at") or now,
        "updated_at": now,
    }

    _pattern_rules[rule_id] = rule

    # Also add to static analyzer if enabled and is literal type
    if rule["enabled"] and rule["type"] == "literal":
        s.static_analyzer.add_rule(rule["pattern"])

    return rule


@app.put("/api/rules/patterns")
async def update_pattern_rule(request: Request) -> dict[str, Any]:
    """Update an existing pattern rule."""
    s = _state(request)
    data = await request.json()
    rule_id = data.get("id")

    if not rule_id or rule_id not in _pattern_rules:
        return {"error": "Rule not found"}

    old_rule = _pattern_rules[rule_id]

    # Remove old pattern from analyzer if it was active
    if old_rule["enabled"] and old_rule["type"] == "literal":
        s.static_analyzer.remove_rule(old_rule["pattern"])

    # Update rule
    rule = {
        **old_rule,
        "name": data.get("name", old_rule["name"]),
        "pattern": data.get("pattern", old_rule["pattern"]),
        "type": data.get("type", old_rule["type"]),
        "action": data.get("action", old_rule["action"]),
        "threat_level": data.get("threat_level", old_rule["threat_level"]),
        "enabled": data.get("enabled", old_rule["enabled"]),
        "description": data.get("description", old_rule["description"]),
        "updated_at": time.time(),
    }

    _pattern_rules[rule_id] = rule

    # Add new pattern to analyzer if enabled and literal
    if rule["enabled"] and rule["type"] == "literal":
        s.static_analyzer.add_rule(rule["pattern"])

    return rule


@app.delete("/api/rules/patterns/{rule_id}")
async def delete_pattern_rule(request: Request, rule_id: str) -> dict[str, Any]:
    """Delete a pattern rule."""
    s = _state(request)

    if rule_id not in _pattern_rules:
        return {"error": "Rule not found"}

    rule = _pattern_rules[rule_id]

    # Remove from analyzer if it was active
    if rule["enabled"] and rule["type"] == "literal":
        s.static_analyzer.remove_rule(rule["pattern"])

    del _pattern_rules[rule_id]

    return {"status": "ok", "deleted": rule_id}


@app.post("/api/rules/patterns/{rule_id}/toggle")
async def toggle_pattern_rule(request: Request, rule_id: str) -> dict[str, Any]:
    """Toggle a pattern rule's enabled state."""
    s = _state(request)
    data = await request.json()

    if rule_id not in _pattern_rules:
        return {"error": "Rule not found"}

    rule = _pattern_rules[rule_id]
    new_enabled = data.get("enabled", not rule["enabled"])

    # Update analyzer accordingly
    if rule["type"] == "literal":
        if new_enabled and not rule["enabled"]:
            s.static_analyzer.add_rule(rule["pattern"])
        elif not new_enabled and rule["enabled"]:
            s.static_analyzer.remove_rule(rule["pattern"])

    rule["enabled"] = new_enabled
    rule["updated_at"] = time.time()

    return rule


@app.post("/api/rules/default")
async def update_default_action(request: Request) -> dict[str, Any]:
    """Update the default action for unmatched requests."""
    global _default_action
    data = await request.json()
    _default_action = data.get("action", "ALLOW")
    return {"status": "ok", "default_action": _default_action}


# ── Audit Log ──────────────────────────────────────────────────


@app.get("/api/audit")
async def get_audit(request: Request) -> list[dict[str, Any]]:
    s = _state(request)
    limit = int(request.query_params.get("limit", 50))
    return await s.audit_logger.get_recent_entries(limit)


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


# ── OpenAI Proxy (Chat Completions) ──────────────────────────────


@app.post("/v1/chat/completions")
async def openai_chat_completions(request: Request) -> StreamingResponse:
    s = _state(request)
    return await s.openai_adapter.handle_chat_completion(request)


# ── OpenAI Proxy (Responses) ─────────────────────────────────────


@app.post("/v1/responses")
async def openai_responses(request: Request) -> StreamingResponse:
    s = _state(request)
    # Reuse the same handler logic if the body is compatible (JSON chat completion)
    return await s.openai_adapter.handle_chat_completion(request)


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


# ── Test Lab ─────────────────────────────────────────────────────


@app.post("/api/test/analyze")
async def test_analyze(request: Request) -> dict[str, Any]:
    from .models import ThreatLevel, DashboardEvent, AnalysisResult
    import json
    import uuid

    s = _state(request)
    data = await request.json()
    payload_str = data.get("payload", "")

    # L1 Analysis
    l1_result = s.static_analyzer.analyze(payload_str)
    l1_verdict = "BLOCK" if l1_result.threat_level != ThreatLevel.NONE else "ALLOW"

    # L2 Analysis
    l2_verdict = "ALLOW"
    l2_confidence = 0.0
    l2_reasoning = ""
    method = "unknown"

    try:
        parsed = json.loads(payload_str)
        method = parsed.get("method", "unknown")
        params = parsed.get("params", {})

        # Run L2 classification
        l2_result = await s.semantic_analyzer.analyze(
            method=method,
            params=params,
            session_context=[],
        )
        l2_confidence = l2_result.confidence
        l2_reasoning = l2_result.reasoning
        if l2_result.is_injection:
            l2_verdict = "BLOCK"
            if l2_result.threat_level == ThreatLevel.CRITICAL:
                l2_verdict = "ESCALATE"
    except json.JSONDecodeError:
        pass

    # Final Verdict Logic
    final_verdict = "ALLOW"
    if l1_verdict != "ALLOW":
        final_verdict = l1_verdict
    elif l2_verdict != "ALLOW":
        final_verdict = l2_verdict

    # Determine threat level
    threat_level = l1_result.threat_level
    if final_verdict == "BLOCK":
        threat_level = ThreatLevel.HIGH
    elif final_verdict == "ESCALATE":
        threat_level = ThreatLevel.CRITICAL

    # Emit dashboard event for test requests
    analysis = AnalysisResult(
        request_id=str(uuid.uuid4()),
        verdict=final_verdict,
        threat_level=threat_level,
        l1_matched_patterns=l1_result.matched_patterns,
        l2_is_injection=(l2_verdict != "ALLOW"),
        l2_confidence=l2_confidence,
        l2_reasoning=l2_reasoning,
        blocked_reason=", ".join(l1_result.matched_patterns) if l1_result.matched_patterns else "",
    )

    event = DashboardEvent(
        event_type="request_analyzed",
        timestamp=time.time(),
        session_id="test-lab",
        agent_id="security-tester",
        method=method,
        payload_preview=payload_str[:200] + ("..." if len(payload_str) > 200 else ""),
        analysis=analysis,
        is_alert=(final_verdict != "ALLOW"),
    )

    await s._emit_dashboard(event)

    # Also log to audit
    from .models import AuditEntry
    audit_entry = AuditEntry(
        id=analysis.request_id,
        timestamp=time.time(),
        session_id="test-lab",
        agent_id="security-tester",
        method=method,
        verdict=final_verdict,
        threat_level=threat_level,
        matched_patterns=l1_result.matched_patterns,
        payload_hash="test",
        payload_preview=payload_str[:500],
    )
    await s._emit_audit(audit_entry)

    return {
        "verdict": final_verdict,
        "l1_patterns": l1_result.matched_patterns,
        "l2_confidence": l2_confidence,
    }


# ── Logging config ───────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
