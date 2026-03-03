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


# ── Gateway Info (auto-discover token from local config) ────────


@app.get("/api/gateway-info")
async def gateway_info() -> dict[str, Any]:
    """Read the local OpenClaw gateway config to auto-provide connection details.

    This endpoint reads ~/.openclaw/openclaw.json to extract the gateway port and
    auth token, so the browser frontend can connect without manual configuration.
    Only works when the firewall backend runs on the same machine as the gateway.
    """
    import json as _json

    config_path = Path.home() / ".openclaw" / "openclaw.json"
    result: dict[str, Any] = {"configured": False}
    if not config_path.exists():
        return result
    try:
        raw = config_path.read_text(encoding="utf-8")
        data = _json.loads(raw)
        gw = data.get("gateway", {})
        if not gw:
            return result
        result["configured"] = True
        result["port"] = gw.get("port", 18789)
        result["bind"] = gw.get("bind", "loopback")
        result["mode"] = gw.get("mode", "local")
        # Pass auth info so the frontend can auto-connect
        auth = gw.get("auth", {})
        if auth.get("token"):
            result["token"] = auth["token"]
        if auth.get("password"):
            result["hasPassword"] = True
        # Pass allowed origins so frontend can self-register
        control_ui = gw.get("controlUi", {})
        result["allowedOrigins"] = control_ui.get("allowedOrigins", [])
    except Exception:
        logging.getLogger(__name__).warning("Failed to read gateway config", exc_info=True)
    return result


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
            rule_id = f"default-{i + 1}"
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
async def get_audit(request: Request) -> JSONResponse:
    """
    Return audit log entries in the format expected by the frontend:
    { "entries": [...], "has_more": boolean }

    Each entry is normalized to include top-level fields that the
    frontend AuditEntry TypeScript type expects (id, threat_level,
    matched_patterns, etc.), extracted from the nested analysis object.
    """
    s = _state(request)
    limit = int(request.query_params.get("limit", 50))
    offset = int(request.query_params.get("offset", 0))
    verdict_filter = request.query_params.get("verdict")
    since_str = request.query_params.get("since")

    raw_entries = await s.audit_logger.get_recent_entries(limit + offset + 1)

    # Apply filters
    if verdict_filter:
        raw_entries = [e for e in raw_entries if str(e.get("verdict", "")).upper() == verdict_filter.upper()]
    if since_str:
        since_ts = float(since_str)
        raw_entries = [e for e in raw_entries if e.get("timestamp", 0) >= since_ts]

    total = len(raw_entries)
    paginated = raw_entries[offset : offset + limit]

    # Transform each entry to match frontend AuditEntry type
    entries = []
    for raw in paginated:
        analysis = raw.get("analysis") or {}
        entries.append(
            {
                "id": analysis.get("request_id", raw.get("session_id", "")),
                "timestamp": raw.get("timestamp", 0),
                "session_id": raw.get("session_id", ""),
                "agent_id": raw.get("agent_id", ""),
                "method": raw.get("method", ""),
                "verdict": str(raw.get("verdict", "ALLOW")).upper(),
                "threat_level": str(analysis.get("threat_level", "NONE")).upper(),
                "matched_patterns": analysis.get("l1_matched_patterns", []),
                "payload_hash": raw.get("session_id", ""),
                "payload_preview": raw.get("params_summary", ""),
            }
        )

    return JSONResponse({"entries": entries, "has_more": total > offset + limit})


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


# ── Red Team Chat Lab ─────────────────────────────────────────────


@app.post("/api/chat/send")
async def chat_send(request: Request) -> JSONResponse:
    """
    Red Team Chat Lab endpoint.

    Accepts a chat message (with optional modified/injected version),
    runs L1/L2 analysis, and optionally forwards to the upstream LLM.

    Request body:
      {
        "messages": [{"role": "user", "content": "..."}],
        "model": "deepseek/deepseek-chat",
        "modified_content": "...",     // optional: injected/modified user content
        "force_forward": false,        // optional: forward even if blocked
        "analyze_only": false          // optional: only analyze, don't forward
      }

    Response:
      {
        "analysis": { "verdict", "l1_patterns", "l2_confidence", ... },
        "blocked": bool,
        "original_content": "...",
        "forwarded_content": "...",    // what was actually sent upstream
        "response": "..." | null,      // LLM response text (null if blocked)
        "response_raw": {...} | null   // full LLM response object
      }
    """
    import uuid

    s = _state(request)
    data = await request.json()
    messages = data.get("messages", [])
    model = data.get("model", "deepseek/deepseek-chat")
    modified_content = data.get("modified_content", None)
    force_forward = data.get("force_forward", False)
    analyze_only = data.get("analyze_only", False)

    if not messages:
        return JSONResponse({"error": "No messages provided"}, status_code=400)

    # Extract original user content
    from .models import ThreatLevel, DashboardEvent, AnalysisResult, AuditEntry

    def _extract_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        return str(content) if content else ""

    original_content = "\n".join(
        [_extract_text(m.get("content", "")) for m in messages if m.get("role") == "user"]
    )

    # Determine what content to analyze (modified version if provided)
    analyze_content = modified_content if modified_content else original_content
    forwarded_messages = list(messages)  # shallow copy

    # If modified content provided, replace the last user message
    if modified_content:
        for i in range(len(forwarded_messages) - 1, -1, -1):
            if forwarded_messages[i].get("role") == "user":
                forwarded_messages[i] = {"role": "user", "content": modified_content}
                break

    # L1 Analysis
    l1_result = s.static_analyzer.analyze(analyze_content)
    l1_blocked = l1_result.threat_level in (ThreatLevel.CRITICAL, ThreatLevel.HIGH)

    # L2 Analysis
    l2_confidence = 0.0
    l2_reasoning = ""
    l2_is_injection = False

    try:
        l2_result = await s.semantic_analyzer.analyze(
            method="chat/completions",
            params=analyze_content,
            session_context=[],
        )
        l2_confidence = l2_result.confidence
        l2_reasoning = l2_result.reasoning
        l2_is_injection = l2_result.is_injection
    except Exception as e:
        l2_reasoning = f"L2 analysis error: {e}"

    l2_blocked = l2_is_injection and l2_confidence >= 0.7

    # Final verdict
    is_blocked = l1_blocked or l2_blocked
    verdict = "BLOCK" if is_blocked else "ALLOW"
    if is_blocked and l2_confidence >= 0.9:
        verdict = "ESCALATE"

    threat_level = l1_result.threat_level
    if l2_blocked:
        threat_level = ThreatLevel.HIGH if l2_confidence < 0.9 else ThreatLevel.CRITICAL

    analysis_result = AnalysisResult(
        request_id=str(uuid.uuid4()),
        verdict=verdict,
        threat_level=threat_level,
        l1_matched_patterns=l1_result.matched_patterns,
        l2_is_injection=l2_is_injection,
        l2_confidence=l2_confidence,
        l2_reasoning=l2_reasoning,
        blocked_reason=(
            f"L1: {', '.join(l1_result.matched_patterns)}"
            if l1_blocked
            else f"L2: {l2_reasoning}"
            if l2_blocked
            else ""
        ),
    )

    # Emit dashboard event
    event = DashboardEvent(
        event_type="chat_lab_request",
        timestamp=time.time(),
        session_id="chat-lab",
        agent_id="red-team-tester",
        method="chat/completions",
        payload_preview=(
            analyze_content[:200] + "..." if len(analyze_content) > 200 else analyze_content
        ),
        analysis=analysis_result,
        is_alert=(verdict != "ALLOW"),
    )
    await s._emit_dashboard(event)

    # Emit audit entry
    audit_entry = AuditEntry(
        timestamp=time.time(),
        session_id="chat-lab",
        agent_id="red-team-tester",
        method="chat/completions",
        params_summary=analyze_content[:500],
        analysis=analysis_result,
        verdict=verdict,
    )
    await s._emit_audit(audit_entry)

    # Build response
    response_data: dict[str, Any] = {
        "analysis": {
            "request_id": analysis_result.request_id,
            "verdict": verdict,
            "threat_level": threat_level.value
            if hasattr(threat_level, "value")
            else str(threat_level),
            "l1_patterns": l1_result.matched_patterns,
            "l2_is_injection": l2_is_injection,
            "l2_confidence": l2_confidence,
            "l2_reasoning": l2_reasoning,
            "blocked_reason": analysis_result.blocked_reason,
        },
        "blocked": is_blocked and not force_forward,
        "original_content": original_content,
        "forwarded_content": analyze_content,
        "response": None,
        "response_raw": None,
    }

    # Forward to upstream if not blocked (or force_forward) and not analyze_only
    if (not is_blocked or force_forward) and not analyze_only:
        try:
            import httpx

            # Use the openai_adapter's upstream URL and API key
            upstream_url = f"{s.openai_adapter.upstream_url}/chat/completions"
            upstream_headers: dict[str, str] = {
                "content-type": "application/json",
                "accept": "application/json",
            }
            if s.openai_adapter.api_key:
                upstream_headers["Authorization"] = f"Bearer {s.openai_adapter.api_key}"

            chat_body = {
                "model": model,
                "messages": forwarded_messages,
                "stream": False,
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    upstream_url,
                    headers=upstream_headers,
                    json=chat_body,
                )

                if resp.status_code == 200:
                    resp_json = resp.json()
                    response_data["response_raw"] = resp_json
                    # Extract text from response
                    choices = resp_json.get("choices", [])
                    if choices:
                        msg = choices[0].get("message", {})
                        response_data["response"] = msg.get("content", "")
                else:
                    response_data["response"] = (
                        f"[Upstream error {resp.status_code}]: {resp.text[:500]}"
                    )
        except Exception as e:
            logger.error(f"Chat lab upstream error: {e}")
            response_data["response"] = f"[Error]: {e}"

    return JSONResponse(response_data)


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
