"""
Firewall configuration — single source of truth for all tunable parameters.

Environment variables override defaults (12-factor style).
All timeouts are in seconds; all sizes are in bytes unless noted.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet


class TransportMode(str, Enum):
    """Supported MCP transport modes."""

    STDIO = "stdio"
    SSE = "sse"
    WEBSOCKET = "websocket"


@dataclass(frozen=True, slots=True)
class FirewallConfig:
    """Immutable runtime configuration. Constructed once at startup."""

    # ── Network ──────────────────────────────────────────────────────
    listen_host: str = field(default_factory=lambda: os.getenv("AF_LISTEN_HOST", "127.0.0.1"))
    listen_port: int = field(default_factory=lambda: int(os.getenv("AF_LISTEN_PORT", "9090")))

    # ── Upstream MCP Server ──────────────────────────────────────────
    upstream_host: str = field(default_factory=lambda: os.getenv("AF_UPSTREAM_HOST", "127.0.0.1"))
    upstream_port: int = field(default_factory=lambda: int(os.getenv("AF_UPSTREAM_PORT", "3000")))
    transport_mode: TransportMode = field(
        default_factory=lambda: TransportMode(os.getenv("AF_TRANSPORT_MODE", "sse"))
    )

    # ── Engine Tuning ────────────────────────────────────────────────
    l1_enabled: bool = field(default_factory=lambda: os.getenv("AF_L1_ENABLED", "1") == "1")
    l2_enabled: bool = field(default_factory=lambda: os.getenv("AF_L2_ENABLED", "1") == "1")
    l2_model_endpoint: str = field(
        default_factory=lambda: os.getenv(
            "AF_L2_MODEL_ENDPOINT", "https://openrouter.ai/api/v1/chat/completions"
        )
    )
    l2_api_key: str = field(default_factory=lambda: os.getenv("AF_L2_API_KEY", ""))
    l2_model: str = field(default_factory=lambda: os.getenv("AF_L2_MODEL", "minimax/minimax-m2.5"))
    l2_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("AF_L2_TIMEOUT", "10.0"))
    )

    # ── Session ──────────────────────────────────────────────────────
    session_ring_buffer_size: int = field(
        default_factory=lambda: int(os.getenv("AF_SESSION_BUFFER_SIZE", "64"))
    )
    session_ttl_seconds: int = field(
        default_factory=lambda: int(os.getenv("AF_SESSION_TTL", "3600"))
    )

    # ── Rate Limiting (token-bucket) ─────────────────────────────────
    rate_limit_requests_per_sec: float = field(
        default_factory=lambda: float(os.getenv("AF_RATE_LIMIT_RPS", "100"))
    )
    rate_limit_burst: int = field(
        default_factory=lambda: int(os.getenv("AF_RATE_LIMIT_BURST", "200"))
    )

    # ── Audit ────────────────────────────────────────────────────────
    audit_log_path: str = field(
        default_factory=lambda: os.getenv("AF_AUDIT_LOG", "./audit/firewall.jsonl")
    )

    # ── Dashboard ────────────────────────────────────────────────────
    dashboard_ws_path: str = "/ws/dashboard"

    # ── Static analyzer high-risk patterns ───────────────────────────
    blocked_commands: FrozenSet[str] = field(
        default_factory=lambda: frozenset(
            os.getenv(
                "AF_BLOCKED_COMMANDS",
                "rm -rf,/etc/shadow,/etc/passwd,DROP TABLE,DELETE FROM,"
                "TRUNCATE,shutdown,mkfs,dd if=,FORMAT C:,wget|sh,curl|bash",
            ).split(",")
        )
    )
