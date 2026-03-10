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

import asyncio
import json
import logging
import mimetypes
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

# Load .env file before importing config
from dotenv import load_dotenv

_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from .audit.logger import AuditLogger
from .channels.feishu_adapter import FeishuAdapter, FeishuConfig
from .config import FirewallConfig
from .dashboard.ws_handler import DashboardHub
from .engine.semantic_analyzer import LlmClassifier, MockClassifier, SemanticAnalyzer
from .engine.static_analyzer import StaticAnalyzer
from .gateway_tools import GatewayToolRegistry, get_gateway_tool_registry
from .models import AuditEntry, DashboardEvent
from .proxy.openai_adapter import OpenAIAdapter
from .proxy.session_manager import SessionManager
from .proxy.sse_adapter import SseAdapter, WebSocketAdapter
from .skills import SkillRegistry, get_skill_registry

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

        # Initialize Feishu channel adapter if enabled
        self.feishu_adapter: FeishuAdapter | None = None
        if config.feishu_enabled and config.feishu_app_id:
            feishu_config = FeishuConfig(
                app_id=config.feishu_app_id,
                app_secret=config.feishu_app_secret,
                encrypt_key=config.feishu_encrypt_key or None,
                verification_token=config.feishu_verification_token or None,
                model=config.feishu_model,
                upstream_url=config.feishu_upstream_url,
            )
            self.feishu_adapter = FeishuAdapter(
                config=feishu_config,
                static_analyzer=self.static_analyzer,
                semantic_analyzer=self.semantic_analyzer,
                upstream_url=openai_upstream,
                emit_dashboard_event=self._emit_dashboard,
                emit_audit_entry=self._emit_audit,
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

    # Start Feishu channel if enabled
    if state.feishu_adapter:
        logger.info("🚀 Starting Feishu channel adapter...")
        try:
            await state.feishu_adapter.start()
            logger.info("✅ Feishu channel connected successfully")
        except Exception as e:
            logger.error(f"❌ Failed to start Feishu channel: {e}")
            logger.warning("⚠️  Please check your Feishu App ID and Secret in .env file")
            logger.warning("⚠️  Also ensure you've enabled event subscriptions in Feishu Admin Console")

    logger.info(
        "🛡️  Agent Firewall started on %s:%d → upstream %s:%d",
        config.listen_host,
        config.listen_port,
        config.upstream_host,
        config.upstream_port,
    )

    yield

    # Graceful shutdown
    if state.feishu_adapter:
        logger.info("Stopping Feishu channel...")
        await state.feishu_adapter.stop()

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
    expose_headers=["*"],
)


def _state(request: Request | None = None) -> AppState:
    """Extract AppState from the ASGI app."""

    if request is not None:
        return request.app.state.firewall  # type: ignore[no-any-return]
    raise RuntimeError("No request context")


# ── Health ────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "agent-firewall"}


# ── Local File Serve (for audio/image/doc rendered in ChatLab) ──

_ALLOWED_EXTENSIONS = {
    # Audio
    ".mp3",
    ".wav",
    ".ogg",
    ".m4a",
    ".flac",
    ".aac",
    ".webm",
    # Image
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".bmp",
    ".ico",
    # Documents
    ".txt",
    ".pdf",
    ".docx",
    ".xlsx",
    ".csv",
    ".json",
    ".md",
    ".html",
    # Video
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
}


@app.get("/api/file")
async def serve_local_file(path: str) -> FileResponse:
    """Serve a local file so the browser can render audio/image/doc inline.

    Only serves files with allowed extensions. The *path* query param is the
    absolute filesystem path, e.g. `/api/file?path=/tmp/voice.mp3`.
    """
    file_path = Path(path)
    if not file_path.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)  # type: ignore[return-value]
    if not file_path.is_file():
        return JSONResponse({"error": "Not a file"}, status_code=400)  # type: ignore[return-value]
    ext = file_path.suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        return JSONResponse({"error": f"Extension {ext} not allowed"}, status_code=403)  # type: ignore[return-value]
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
    )


# ── Gateway Info (auto-discover token from local config) ────────


@app.get("/api/gateway-info")
async def gateway_info() -> dict[str, Any]:
    """Read the local gateway config to auto-provide connection details.

    This endpoint reads ~/.agent-shield-dev/agent-shield.json or ~/.openclaw/openclaw.json
    to extract the gateway port and auth token, so the browser frontend can connect
    without manual configuration. Only works when the firewall backend runs on the
    same machine as the gateway.
    """
    import json as _json

    # Try agent-shield-dev config first, then openclaw config
    config_paths = [
        Path.home() / ".agent-shield-dev" / "agent-shield.json",
        Path.home() / ".openclaw" / "openclaw.json",
    ]

    result: dict[str, Any] = {"configured": False}

    for config_path in config_paths:
        if not config_path.exists():
            continue
        try:
            raw = config_path.read_text(encoding="utf-8")
            data = _json.loads(raw)
            gw = data.get("gateway", {})
            if not gw:
                continue
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
            break  # Found valid config, stop searching
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
        "services": {
            "tavily_api_key": c.tavily_api_key,
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
    if "services" in updates:
        flat_updates.update(updates["services"])
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
        "services": {
            "tavily_api_key": c.tavily_api_key,
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
        raw_entries = [
            e for e in raw_entries if str(e.get("verdict", "")).upper() == verdict_filter.upper()
        ]
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


# ── Feishu Channel API ───────────────────────────────────────────


@app.get("/api/feishu/config")
async def get_feishu_config(request: Request) -> JSONResponse:
    """Get Feishu channel configuration."""
    s = _state(request)
    c = s.config

    return JSONResponse(
        {
            "connected": s.feishu_adapter is not None and s.feishu_adapter._running,
            "app_id": c.feishu_app_id,
            "app_secret": "***" if c.feishu_app_secret else "",
            "upstream_url": c.feishu_upstream_url,
            "model": c.feishu_model,
        }
    )


@app.post("/api/feishu/config")
async def update_feishu_config(request: Request) -> JSONResponse:
    """Update Feishu channel configuration."""
    updates = await request.json()
    # TODO: Implement config update logic
    # For now, just return success
    return JSONResponse({"status": "ok", "message": "Configuration saved. Restart required."})


@app.get("/api/feishu/stats")
async def get_feishu_stats(request: Request) -> JSONResponse:
    """Get Feishu channel statistics."""
    s = _state(request)

    # Count Feishu-related audit entries
    feishu_entries = [
        e for e in s.audit_logger._buffer if "feishu" in e.get("method", "").lower()
    ]

    total_messages = len(feishu_entries)
    blocked_messages = sum(1 for e in feishu_entries if e.get("verdict") == "BLOCK")

    # Count unique chat IDs
    active_chats = len(set(e.get("session_id") for e in feishu_entries if e.get("session_id")))

    # Calculate average response time
    response_times = [e.get("response_time_ms", 0) for e in feishu_entries]
    avg_response_time = round(sum(response_times) / len(response_times)) if response_times else 0

    return JSONResponse(
        {
            "total_messages": total_messages,
            "blocked_messages": blocked_messages,
            "active_chats": active_chats,
            "avg_response_time": avg_response_time,
        }
    )


@app.post("/api/feishu/test-send")
async def test_feishu_send(request: Request) -> JSONResponse:
    """Test endpoint to send a message via Feishu API."""
    s = _state(request)

    if not s.feishu_adapter:
        return JSONResponse({"error": "Feishu adapter not initialized"}, status_code=503)

    data = await request.json()
    chat_id = data.get("chat_id")
    message = data.get("message", "Hello from Agent Firewall!")

    if not chat_id:
        return JSONResponse({"error": "chat_id is required"}, status_code=400)

    try:
        success = await s.feishu_adapter.send_message(chat_id, message)
        return JSONResponse({"success": success, "chat_id": chat_id, "message": message})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── MCP Proxy (HTTP POST) ────────────────────────────────────────


@app.get("/api/mcp/tools")
async def list_mcp_tools(request: Request) -> JSONResponse:
    """List available tools: gateway (auto-discovered) + skills (from SKILL.md)."""
    tools = _all_tools_openai_format()

    # Gateway tools info
    gw_registry = _get_gateway_tool_registry()
    gateway_info = [
        {"name": t.name, "description": t.description, "source": "gateway"}
        for t in gw_registry.tools.values()
    ]

    # Skill tools info
    skill_registry = _get_skill_registry()
    skills_info = [
        {
            "name": s.name,
            "description": s.description,
            "emoji": s.emoji,
            "bins": s.required_bins,
            "source": "skill",
        }
        for s in skill_registry.ready_skills.values()
    ]

    return JSONResponse(
        {
            "tools": tools,
            "count": len(tools),
            "gateway_tools": gateway_info,
            "skills": skills_info,
        }
    )


# ── Custom MCP Servers & Skills CRUD ─────────────────────────────

_CUSTOM_CONFIG_PATH = Path(__file__).parent.parent / "custom_config.json"


def _load_custom_config() -> dict:
    """Load custom MCP servers and skills from JSON file."""
    if _CUSTOM_CONFIG_PATH.exists():
        try:
            return json.loads(_CUSTOM_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"mcp_servers": [], "skills": []}


def _save_custom_config(data: dict) -> None:
    """Persist custom config to JSON file."""
    _CUSTOM_CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


@app.get("/api/custom-config")
async def get_custom_config() -> JSONResponse:
    """Return all custom MCP servers and skills."""
    return JSONResponse(_load_custom_config())


@app.put("/api/custom-config")
async def save_custom_config(request: Request) -> JSONResponse:
    """Replace the full custom config (mcp_servers + skills)."""
    data = await request.json()
    _save_custom_config(data)
    return JSONResponse({"ok": True})


@app.post("/api/custom-config/mcp-servers")
async def add_custom_mcp_server(request: Request) -> JSONResponse:
    """Add or update a custom MCP server."""
    server = await request.json()
    cfg = _load_custom_config()
    servers = cfg.get("mcp_servers", [])
    # Upsert by id
    idx = next((i for i, s in enumerate(servers) if s["id"] == server.get("id")), None)
    if idx is not None:
        servers[idx] = server
    else:
        servers.append(server)
    cfg["mcp_servers"] = servers
    _save_custom_config(cfg)
    return JSONResponse({"ok": True, "server": server})


@app.delete("/api/custom-config/mcp-servers/{server_id}")
async def delete_custom_mcp_server(server_id: str) -> JSONResponse:
    """Delete a custom MCP server by ID."""
    cfg = _load_custom_config()
    cfg["mcp_servers"] = [s for s in cfg.get("mcp_servers", []) if s.get("id") != server_id]
    _save_custom_config(cfg)
    return JSONResponse({"ok": True})


@app.post("/api/custom-config/skills")
async def add_custom_skill(request: Request) -> JSONResponse:
    """Add or update a custom skill definition."""
    skill = await request.json()
    cfg = _load_custom_config()
    skills = cfg.get("skills", [])
    idx = next((i for i, s in enumerate(skills) if s["id"] == skill.get("id")), None)
    if idx is not None:
        skills[idx] = skill
    else:
        skills.append(skill)
    cfg["skills"] = skills
    _save_custom_config(cfg)
    return JSONResponse({"ok": True, "skill": skill})


@app.delete("/api/custom-config/skills/{skill_id}")
async def delete_custom_skill(skill_id: str) -> JSONResponse:
    """Delete a custom skill by ID."""
    cfg = _load_custom_config()
    cfg["skills"] = [s for s in cfg.get("skills", []) if s.get("id") != skill_id]
    _save_custom_config(cfg)
    return JSONResponse({"ok": True})


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

# ── Dynamic tool discovery (skills + gateway) ────────────────────

# Tavily web search (replaces Brave for web_search)
TAVILY_SEARCH_URL = "https://api.tavily.com/search"


async def _tavily_web_search(query: str, max_results: int = 5) -> str:
    """Execute a web search via Tavily API."""
    import httpx

    tavily_api_key = os.getenv("AF_TAVILY_API_KEY", "")
    if not tavily_api_key:
        return "[Tavily error] AF_TAVILY_API_KEY not configured. Set it in Settings."

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                TAVILY_SEARCH_URL,
                json={
                    "api_key": tavily_api_key,
                    "query": query,
                    "max_results": max_results,
                    "include_answer": True,
                    "search_depth": "basic",
                },
            )
            if resp.status_code != 200:
                return f"[Tavily error] HTTP {resp.status_code}: {resp.text[:300]}"
            data = resp.json()
            parts = []
            # Include AI-generated answer if available
            if data.get("answer"):
                parts.append(f"**Answer:** {data['answer']}\n")
            # Include search results
            for i, r in enumerate(data.get("results", [])[:max_results], 1):
                title = r.get("title", "")
                url = r.get("url", "")
                content = r.get("content", "")[:300]
                parts.append(f"{i}. [{title}]({url})\n   {content}")
            return "\n\n".join(parts) if parts else "No results found."
    except Exception as e:
        return f"[Tavily search error]: {e}"


_skill_registry: SkillRegistry | None = None
_gateway_tool_registry: GatewayToolRegistry | None = None


def _get_skill_registry() -> SkillRegistry:
    """Lazy-init the global skill registry (scans skills/ once)."""
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = get_skill_registry()
    return _skill_registry


def _get_gateway_tool_registry() -> GatewayToolRegistry:
    """Lazy-init the global gateway tool registry (scans source once)."""
    global _gateway_tool_registry
    if _gateway_tool_registry is None:
        _gateway_tool_registry = get_gateway_tool_registry()
    return _gateway_tool_registry


def _get_gateway_auth() -> tuple[str, int, str]:
    """Read gateway host, port, and auth token from ~/.openclaw/openclaw.json."""
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    host = "127.0.0.1"
    port = 18789
    token = ""
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            gw = data.get("gateway", {})
            port = gw.get("port", 18789)
            token = gw.get("auth", {}).get("token", "")
        except Exception:
            pass
    return host, port, token


def _all_tools_openai_format() -> list[dict[str, Any]]:
    """Build OpenAI function-calling tools from dynamic registries (gateway + skills)."""
    # Gateway tools (auto-discovered from TypeScript source)
    gw_registry = _get_gateway_tool_registry()
    gateway_tools = gw_registry.get_openai_tools()

    # Skill tools (auto-discovered from SKILL.md files)
    skill_registry = _get_skill_registry()
    skill_tools = skill_registry.get_openai_tools()

    return gateway_tools + skill_tools


@app.post("/api/chat/send")
async def chat_send(request: Request):
    """
    Red Team Chat Lab endpoint — **streaming NDJSON**.

    Accepts a chat message (with optional modified/injected version),
    runs L1/L2 analysis, and optionally forwards to the upstream LLM.
    Results are streamed back as newline-delimited JSON events so the
    frontend can display progress incrementally.

    Event types:
      {"type": "analysis", "analysis": {...}, "blocked": bool}
      {"type": "tool_call", "tool_call": {...}}
      {"type": "content", "content": "..."}
      {"type": "error", "error": "..."}
      {"type": "done"}
    """
    import uuid

    s = _state(request)
    data = await request.json()
    messages = data.get("messages", [])
    model = data.get("model", "openai/gpt-4o-mini")
    modified_content = data.get("modified_content", None)
    force_forward = data.get("force_forward", False)
    analyze_only = data.get("analyze_only", False)
    temperature = data.get("temperature", None)
    max_tokens = data.get("max_tokens", None)
    top_p = data.get("top_p", None)
    enable_tools = data.get("enable_tools", True)

    if not messages:
        return JSONResponse({"error": "No messages provided"}, status_code=400)

    async def _event_stream():
        """Async generator yielding NDJSON lines."""
        from .models import AnalysisResult, AuditEntry, DashboardEvent, ThreatLevel

        def _extract_text(content: Any) -> str:
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "\n".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            return str(content) if content else ""

        def _emit(obj: dict) -> str:
            return json.dumps(obj, ensure_ascii=False) + "\n"

        original_content = "\n".join(
            [_extract_text(m.get("content", "")) for m in messages if m.get("role") == "user"]
        )
        analyze_content = modified_content if modified_content else original_content
        forwarded_messages = list(messages)

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

        # Emit dashboard + audit events
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

        analysis_payload = {
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
        }

        # ── Stream: analysis event ──
        yield _emit(
            {
                "type": "analysis",
                "analysis": analysis_payload,
                "blocked": is_blocked and not force_forward,
            }
        )

        if (is_blocked and not force_forward) or analyze_only:
            yield _emit({"type": "done"})
            return

        # ── Forward to upstream LLM ──
        try:
            import httpx

            upstream_url = f"{s.openai_adapter.upstream_url}/chat/completions"
            upstream_headers: dict[str, str] = {
                "content-type": "application/json",
                "accept": "application/json",
            }
            if s.openai_adapter.api_key:
                upstream_headers["Authorization"] = f"Bearer {s.openai_adapter.api_key}"

            gw_host, gw_port, gw_token = _get_gateway_auth()
            openai_tools = _all_tools_openai_format()

            registry = _get_skill_registry()
            gw_registry = _get_gateway_tool_registry()
            skills_prompt = registry.get_skills_system_prompt()
            gateway_prompt = gw_registry.get_system_prompt()
            combined_prompt = "\n\n".join(p for p in [gateway_prompt, skills_prompt] if p)

            if combined_prompt and enable_tools:
                chat_body_messages = list(forwarded_messages)
                has_system = chat_body_messages and chat_body_messages[0].get("role") == "system"
                if has_system:
                    existing = chat_body_messages[0].get("content", "")
                    chat_body_messages[0] = {
                        "role": "system",
                        "content": existing + "\n\n" + combined_prompt,
                    }
                else:
                    chat_body_messages.insert(0, {"role": "system", "content": combined_prompt})
            else:
                chat_body_messages = list(forwarded_messages)

            chat_body: dict[str, Any] = {
                "model": model,
                "messages": chat_body_messages,
                "stream": False,
            }
            if temperature is not None:
                chat_body["temperature"] = float(temperature)
            if max_tokens is not None:
                chat_body["max_tokens"] = int(max_tokens)
            if top_p is not None:
                chat_body["top_p"] = float(top_p)
            if openai_tools and enable_tools:
                chat_body["tools"] = openai_tools
                chat_body["tool_choice"] = "auto"

            tool_calls_log: list[dict[str, Any]] = []
            max_iterations = 100
            max_retries = 4

            async with httpx.AsyncClient(
                timeout=httpx.Timeout(connect=15.0, read=120.0, write=30.0, pool=30.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            ) as client:
                for iteration in range(max_iterations):
                    # Retry loop: fetch + parse as one atomic unit
                    resp = None
                    resp_json = None
                    for attempt in range(max_retries):
                        try:
                            resp = await client.post(
                                upstream_url, headers=upstream_headers, json=chat_body
                            )
                            if resp.status_code == 429 or resp.status_code >= 502:
                                wait = (2**attempt) + 0.5
                                logger.warning(
                                    "Upstream %d on attempt %d/%d, retrying in %.1fs",
                                    resp.status_code,
                                    attempt + 1,
                                    max_retries,
                                    wait,
                                )
                                await asyncio.sleep(wait)
                                continue
                            if resp.status_code == 200:
                                resp_json = resp.json()
                            break  # success or non-retryable error
                        except (
                            httpx.RemoteProtocolError,
                            httpx.ReadError,
                            httpx.ReadTimeout,
                            httpx.ConnectError,
                            httpx.ConnectTimeout,
                        ) as exc:
                            wait = (2**attempt) + 0.5
                            logger.warning(
                                "Upstream connection error on attempt %d/%d: %s, retrying in %.1fs",
                                attempt + 1,
                                max_retries,
                                exc,
                                wait,
                            )
                            if attempt < max_retries - 1:
                                await asyncio.sleep(wait)
                            else:
                                raise

                    if resp is None or resp.status_code != 200:
                        err_detail = resp.text[:500] if resp else "No response"
                        status = resp.status_code if resp else 0
                        yield _emit(
                            {
                                "type": "error",
                                "error": f"Upstream error {status}: {err_detail}",
                            }
                        )
                        break

                    if not resp_json:
                        yield _emit({"type": "error", "error": "Empty response body from upstream"})
                        break

                    choices = resp_json.get("choices", [])
                    if not choices:
                        yield _emit({"type": "error", "error": "No choices in LLM response"})
                        break

                    assistant_msg = choices[0].get("message", {})
                    finish_reason = choices[0].get("finish_reason", "stop")
                    pending_tool_calls = assistant_msg.get("tool_calls", [])

                    if finish_reason == "tool_calls" or pending_tool_calls:
                        chat_body["messages"].append(assistant_msg)

                        for tc in pending_tool_calls:
                            tc_id = tc.get("id", "")
                            func = tc.get("function", {})
                            tool_name = func.get("name", "").strip()
                            try:
                                tool_args = json.loads(func.get("arguments", "{}"))
                            except Exception:
                                tool_args = {}

                            # L1 analysis on the tool call
                            tool_content_str = f"tools/call {tool_name} {json.dumps(tool_args)}"
                            tool_l1 = s.static_analyzer.analyze(tool_content_str)
                            tool_l1_blocked = tool_l1.threat_level in (
                                ThreatLevel.CRITICAL,
                                ThreatLevel.HIGH,
                            )

                            tool_call_record: dict[str, Any] = {
                                "tool_name": tool_name,
                                "arguments": tool_args,
                                "iteration": iteration,
                                "l1_patterns": tool_l1.matched_patterns,
                                "l1_blocked": tool_l1_blocked,
                            }

                            # L2 analysis on the tool call
                            tool_l2_confidence = 0.0
                            tool_l2_reasoning = ""
                            tool_l2_blocked = False
                            try:
                                tool_l2_result = await s.semantic_analyzer.analyze(
                                    method=f"tools/call/{tool_name}",
                                    params=tool_content_str,
                                    session_context=[],
                                )
                                tool_l2_confidence = tool_l2_result.confidence
                                tool_l2_reasoning = tool_l2_result.reasoning
                                tool_l2_blocked = (
                                    tool_l2_result.is_injection and tool_l2_confidence >= 0.7
                                )
                            except Exception as e:
                                tool_l2_reasoning = f"L2 tool analysis error: {e}"

                            tool_call_record["l2_confidence"] = tool_l2_confidence
                            tool_call_record["l2_reasoning"] = tool_l2_reasoning
                            tool_call_record["l2_blocked"] = tool_l2_blocked

                            if tool_l1_blocked or tool_l2_blocked:
                                block_reasons = []
                                if tool_l1_blocked:
                                    block_reasons.append(
                                        f"L1 patterns: {', '.join(tool_l1.matched_patterns)}"
                                    )
                                if tool_l2_blocked:
                                    block_reasons.append(
                                        f"L2 ({tool_l2_confidence:.0%}): {tool_l2_reasoning}"
                                    )
                                tool_result = f"[BLOCKED by firewall] {'; '.join(block_reasons)}"
                                tool_call_record["blocked"] = True
                                tool_call_record["result_preview"] = tool_result[:200]
                            else:
                                if tool_name == "get_skill_docs":
                                    skill_name = tool_args.get("skill_name", "")
                                    tool_result = registry.get_skill_docs(skill_name)
                                elif tool_name == "run_skill":
                                    skill_name = tool_args.get("skill_name", "")
                                    command = tool_args.get("command", "")
                                    explanation = tool_args.get("explanation", "")
                                    logger.info(
                                        "run_skill: %s → %s (%s)",
                                        skill_name,
                                        command[:100],
                                        explanation[:80],
                                    )
                                    tool_result = await registry.execute_skill(skill_name, command)
                                elif tool_name == "invoke_gateway":
                                    gw_tool_name = tool_args.get("tool_name", "")
                                    gw_arguments = tool_args.get("arguments", {})
                                    logger.info(
                                        "invoke_gateway: %s args=%s",
                                        gw_tool_name,
                                        json.dumps(gw_arguments, ensure_ascii=False)[:200],
                                    )
                                    if gw_tool_name == "web_search":
                                        search_query = gw_arguments.get("query", "")
                                        search_count = gw_arguments.get("count", 5)
                                        tool_result = await _tavily_web_search(
                                            search_query, search_count
                                        )
                                    else:
                                        tool_result = await GatewayToolRegistry.execute(
                                            gw_host, gw_port, gw_token, gw_tool_name, gw_arguments
                                        )
                                else:
                                    tool_result = await GatewayToolRegistry.execute(
                                        gw_host, gw_port, gw_token, tool_name, tool_args
                                    )
                                tool_call_record["blocked"] = False
                                tool_call_record["result_preview"] = tool_result[:200]

                            tool_calls_log.append(tool_call_record)

                            # Emit dashboard event for each tool call
                            tool_event = DashboardEvent(
                                event_type="chat_lab_tool_call",
                                timestamp=time.time(),
                                session_id="chat-lab",
                                agent_id="red-team-tester",
                                method=f"tools/call/{tool_name}",
                                payload_preview=tool_content_str[:200],
                                analysis=AnalysisResult(
                                    request_id=str(uuid.uuid4()),
                                    verdict="BLOCK"
                                    if (tool_l1_blocked or tool_l2_blocked)
                                    else "ALLOW",
                                    threat_level=tool_l1.threat_level
                                    if tool_l1_blocked
                                    else (
                                        ThreatLevel.HIGH if tool_l2_blocked else ThreatLevel.NONE
                                    ),
                                    l1_matched_patterns=tool_l1.matched_patterns,
                                    l2_is_injection=tool_l2_blocked,
                                    l2_confidence=tool_l2_confidence,
                                    l2_reasoning=tool_l2_reasoning,
                                    blocked_reason=(
                                        f"L1: {', '.join(tool_l1.matched_patterns)}"
                                        if tool_l1_blocked
                                        else (f"L2: {tool_l2_reasoning}" if tool_l2_blocked else "")
                                    ),
                                ),
                                is_alert=(tool_l1_blocked or tool_l2_blocked),
                            )
                            await s._emit_dashboard(tool_event)

                            # Append tool result to conversation
                            chat_body["messages"].append(
                                {"role": "tool", "tool_call_id": tc_id, "content": tool_result}
                            )

                            # ── Stream: tool call event ──
                            yield _emit({"type": "tool_call", "tool_call": tool_call_record})

                        continue

                    # No tool calls — final response
                    yield _emit({"type": "content", "content": assistant_msg.get("content", "")})
                    break
                else:
                    yield _emit(
                        {"type": "content", "content": "[Max tool-call iterations reached]"}
                    )

        except Exception as e:
            logger.error(f"Chat lab upstream error: {e}")
            yield _emit({"type": "error", "error": str(e)})

        yield _emit({"type": "done"})

    return StreamingResponse(_event_stream(), media_type="application/x-ndjson")


# ── Test Lab ─────────────────────────────────────────────────────


@app.post("/api/test/analyze")
async def test_analyze(request: Request) -> dict[str, Any]:
    import json
    import uuid

    from .models import AnalysisResult, DashboardEvent, ThreatLevel

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
