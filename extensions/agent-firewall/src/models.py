"""
Domain models for the Agent Firewall.

All MCP traffic is JSON-RPC 2.0 — we model it precisely so that the
interceptor never operates on untyped dicts. Pydantic v2 with
model_validator ensures zero-copy-friendly parsing via orjson.

References:
  • JSON-RPC 2.0 Spec — https://www.jsonrpc.org/specification
  • MCP Spec — https://spec.modelcontextprotocol.io/
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Literal

import orjson
from pydantic import BaseModel, ConfigDict, Field, model_validator

# ────────────────────────────────────────────────────────────────────
# JSON-RPC 2.0 Packets
# ────────────────────────────────────────────────────────────────────


class JsonRpcRequest(BaseModel):
    """
    Inbound JSON-RPC 2.0 request from an Agent.

    We deliberately keep `params` as Any here to support MCP's diverse
    tool schemas while avoiding premature deserialization cost.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    jsonrpc: Literal["2.0"] = "2.0"
    method: str
    params: Any = None
    id: str | int | None = None  # notifications have no id

    @model_validator(mode="before")
    @classmethod
    def _coerce_from_bytes(cls, data: Any) -> Any:
        """Allow direct construction from raw bytes (zero-copy parse)."""
        if isinstance(data, (bytes, bytearray, memoryview)):
            return orjson.loads(data)
        return data


class JsonRpcError(BaseModel):
    """Standard JSON-RPC 2.0 error object."""

    code: int
    message: str
    data: Any = None


class JsonRpcResponse(BaseModel):
    """Outbound JSON-RPC 2.0 response to an Agent."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    jsonrpc: Literal["2.0"] = "2.0"
    result: Any = None
    error: JsonRpcError | None = None
    id: str | int | None = None

    def to_bytes(self) -> bytes:
        """Serialize to bytes via orjson for minimal allocation."""
        return orjson.dumps(self.model_dump(exclude_none=True))


# ────────────────────────────────────────────────────────────────────
# Firewall Decision Model
# ────────────────────────────────────────────────────────────────────


class Verdict(str, Enum):
    """Firewall decision on a given request."""

    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"  # requires human review via dashboard


class ThreatLevel(str, Enum):
    """Severity classification of detected threats."""

    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnalysisResult(BaseModel):
    """
    Combined output from the dual analysis engine.

    This is the single data structure that the Policy Enforcer consumes
    to make ALLOW / BLOCK / ESCALATE decisions.
    """

    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = Field(default_factory=time.time)

    # L1 static analysis
    l1_matched_patterns: list[str] = Field(default_factory=list)
    l1_threat_level: ThreatLevel = ThreatLevel.NONE

    # L2 semantic analysis
    l2_is_injection: bool = False
    l2_confidence: float = 0.0
    l2_reasoning: str = ""

    # Final verdict (set by policy enforcer)
    verdict: Verdict = Verdict.ALLOW
    threat_level: ThreatLevel = ThreatLevel.NONE
    blocked_reason: str = ""


# ────────────────────────────────────────────────────────────────────
# Session & Audit Models
# ────────────────────────────────────────────────────────────────────


class SessionContext(BaseModel):
    """
    Reconstructed conversation context for a single Agent ↔ Server session.

    The ring buffer keeps the last N messages to bound memory while
    preserving enough context for the semantic analyzer.
    """

    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    agent_id: str = ""
    created_at: float = Field(default_factory=time.time)
    last_active: float = Field(default_factory=time.time)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    max_messages: int = 64

    def push_message(self, role: str, content: Any) -> None:
        """Append a message, evicting the oldest if buffer is full."""
        self.messages.append({"role": role, "content": content, "ts": time.time()})
        if len(self.messages) > self.max_messages:
            # Ring-buffer eviction — O(1) amortized with list slicing
            self.messages = self.messages[-self.max_messages :]
        self.last_active = time.time()


class AuditEntry(BaseModel):
    """Immutable audit log record written to JSONL."""

    timestamp: float = Field(default_factory=time.time)
    session_id: str = ""
    agent_id: str = ""
    method: str = ""
    params_summary: str = ""
    analysis: AnalysisResult = Field(default_factory=AnalysisResult)
    verdict: Verdict = Verdict.ALLOW
    response_time_ms: float = 0.0

    def to_jsonl(self) -> bytes:
        """Serialize to a single JSONL line (newline-terminated)."""
        return orjson.dumps(self.model_dump()) + b"\n"


# ────────────────────────────────────────────────────────────────────
# MCP-Specific Structures
# ────────────────────────────────────────────────────────────────────


class McpToolCall(BaseModel):
    """
    Parsed representation of an MCP `tools/call` invocation.

    This is the primary structure that the interceptor decomposes
    from the generic JSON-RPC params for deep inspection.
    """

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_jsonrpc_params(cls, params: Any) -> McpToolCall | None:
        """
        Extract tool call info from raw JSON-RPC params.

        Returns None if the params don't represent a tool call
        (e.g., it's a `initialize` or `resources/list` request).
        """
        if not isinstance(params, dict):
            return None
        name = params.get("name")
        if name is None:
            return None
        return cls(name=name, arguments=params.get("arguments", {}))


class DashboardEvent(BaseModel):
    """Real-time event pushed to the God Mode Console via WebSocket."""

    event_type: str  # "request" | "response" | "alert" | "verdict"
    timestamp: float = Field(default_factory=time.time)
    session_id: str = ""
    agent_id: str = ""
    method: str = ""
    payload_preview: str = ""
    analysis: AnalysisResult | None = None
    is_alert: bool = False

    def to_bytes(self) -> bytes:
        return orjson.dumps(self.model_dump(exclude_none=True))


# ────────────────────────────────────────────────────────────────────
# Storage Models (Phase 1)
# ────────────────────────────────────────────────────────────────────


class Trace(BaseModel):
    """
    Complete trace of a single MCP request-response cycle.

    A trace captures the full lifecycle of a request:
    - Original JSON-RPC request
    - Analysis results (L1, L2, Agent-Scan)
    - Verdict and policy decision
    - Response (if any)
    - Metadata (session, timing, etc.)
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    session_id: str
    agent_id: str = ""
    method: str
    params: Any = None
    analysis: AnalysisResult
    verdict: Verdict
    response: JsonRpcResponse | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class Dataset(BaseModel):
    """
    Collection of traces for analysis and policy testing.

    Datasets organize traces into logical groups for:
    - Policy development and testing
    - Security analysis
    - Compliance auditing
    - Training and documentation
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str
    description: str = ""
    is_public: bool = False
    traces: list[str] = Field(default_factory=list)  # List of trace IDs
    policies: list[str] = Field(default_factory=list)  # List of policy IDs
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class Annotation(BaseModel):
    """
    Address-based annotation on a trace.

    Annotations allow users to add notes, highlights, and comments
    to specific parts of a trace. The address field uses a path-like
    syntax to reference specific locations:

    Examples:
        "messages.0.content:10-20"  # Characters 10-20 in first message
        "analysis.l1_matched_patterns"  # L1 analysis results
        "request.params.arguments"  # Tool call arguments
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    trace_id: str
    address: str  # Path to the annotated element
    content: str  # Annotation text
    severity: str = "info"  # "info" | "warning" | "error"
    source: str = "user"  # "user" | "l1" | "l2" | "policy" | "agent_scan"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class Policy(BaseModel):
    """
    Security policy definition.

    Policies define rules for analyzing and filtering MCP traffic.
    They can be written in a simple DSL or Python code.

    Example DSL:
        raise "High risk detected" if:
            threat_level >= "HIGH"

        raise "Dangerous tool call" if:
            tool_call.name in ["execute_code", "file_write"]
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str
    description: str = ""
    code: str  # Policy code (DSL or Python)
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

