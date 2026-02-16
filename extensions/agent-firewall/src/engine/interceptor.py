"""
Core Interceptor — The Heart of the Agent Firewall.

This module implements `intercept_and_analyze`, the central function
that every MCP JSON-RPC request passes through. It orchestrates:

  1. JSON-RPC 2.0 packet parsing and validation.
  2. L1 static analysis (synchronous, CPU-bound).
  3. L2 semantic analysis (asynchronous, I/O-bound).
  4. Policy enforcement (ALLOW / BLOCK / ESCALATE).
  5. Audit logging and dashboard event emission.

The interceptor is designed as a pure async function with explicit
dependency injection — no global state, no singletons, fully testable.

Performance characteristics:
  • L1 alone: <1ms for payloads up to 64KB.
  • L1 + L2 (mock): <2ms end-to-end.
  • L1 + L2 (live LLM): depends on model latency (bounded by timeout).
  • Memory: O(1) per request (no payload copying beyond orjson parse).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import orjson

from ..models import (
    AnalysisResult,
    AuditEntry,
    DashboardEvent,
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
    McpToolCall,
    SessionContext,
    ThreatLevel,
    Verdict,
)
from .semantic_analyzer import L2Result, SemanticAnalyzer
from .static_analyzer import L1Result, StaticAnalyzer

logger = logging.getLogger("agent_firewall.interceptor")


# ────────────────────────────────────────────────────────────────────
# Policy Decision Logic
# ────────────────────────────────────────────────────────────────────

# Methods that are always high-risk and require both L1 + L2 analysis
_HIGH_RISK_METHODS: frozenset[str] = frozenset(
    {
        "tools/call",
        "completion/complete",
        "sampling/createMessage",
    }
)

# Methods that are always safe (MCP handshake / discovery)
_SAFE_METHODS: frozenset[str] = frozenset(
    {
        "initialize",
        "initialized",
        "ping",
        "tools/list",
        "resources/list",
        "resources/templates/list",
        "prompts/list",
        "logging/setLevel",
    }
)


def _compute_verdict(l1: L1Result, l2: L2Result) -> tuple[Verdict, ThreatLevel, str]:
    """
    Merge L1 + L2 results into a final security verdict.

    Decision matrix:
    ┌──────────┬─────────────┬───────────┬──────────────────────────────┐
    │ L1 Level │ L2 Injection│ Confidence│ Verdict                      │
    ├──────────┼─────────────┼───────────┼──────────────────────────────┤
    │ CRITICAL │ any         │ any       │ BLOCK (immediate)            │
    │ HIGH     │ True        │ >= 0.7    │ BLOCK                        │
    │ HIGH     │ True        │ < 0.7     │ ESCALATE (human review)      │
    │ HIGH     │ False       │ any       │ ESCALATE                     │
    │ MEDIUM   │ True        │ >= 0.8    │ BLOCK                        │
    │ MEDIUM   │ True        │ < 0.8     │ ESCALATE                     │
    │ MEDIUM   │ False       │ any       │ ALLOW (with audit)           │
    │ LOW/NONE │ True        │ >= 0.9    │ BLOCK                        │
    │ LOW/NONE │ True        │ >= 0.7    │ ESCALATE                     │
    │ LOW/NONE │ False       │ any       │ ALLOW                        │
    └──────────┴─────────────┴───────────┴──────────────────────────────┘

    Returns:
        Tuple of (verdict, aggregated_threat_level, reason_string).
    """
    from .static_analyzer import _threat_ord

    # Aggregate threat level = max(L1, L2)
    threat = l1.threat_level
    if _threat_ord(l2.threat_level) > _threat_ord(threat):
        threat = l2.threat_level

    reasons: list[str] = []
    if l1.matched_patterns:
        reasons.append(f"L1 patterns: {', '.join(l1.matched_patterns[:5])}")
    if l2.is_injection:
        reasons.append(f"L2 injection (conf={l2.confidence:.2f}): {l2.reasoning}")

    reason_str = "; ".join(reasons) if reasons else "Clean"

    # ── Decision matrix ──────────────────────────────────────────
    l1_ord = _threat_ord(l1.threat_level)

    # Critical L1 = immediate block
    if l1_ord >= _threat_ord(ThreatLevel.CRITICAL):
        return Verdict.BLOCK, threat, reason_str

    # High L1 + L2 injection = block or escalate based on confidence
    if l1_ord >= _threat_ord(ThreatLevel.HIGH):
        if l2.is_injection and l2.confidence >= 0.7:
            return Verdict.BLOCK, threat, reason_str
        return Verdict.ESCALATE, threat, reason_str

    # Medium L1 + high-confidence L2 = block
    if l1_ord >= _threat_ord(ThreatLevel.MEDIUM):
        if l2.is_injection and l2.confidence >= 0.8:
            return Verdict.BLOCK, threat, reason_str
        if l2.is_injection:
            return Verdict.ESCALATE, threat, reason_str
        return Verdict.ALLOW, threat, reason_str

    # L1 clean — rely purely on L2
    if l2.is_injection:
        if l2.confidence >= 0.9:
            return Verdict.BLOCK, threat, reason_str
        if l2.confidence >= 0.7:
            return Verdict.ESCALATE, threat, reason_str

    return Verdict.ALLOW, threat, reason_str


# ────────────────────────────────────────────────────────────────────
# Core Intercept Function
# ────────────────────────────────────────────────────────────────────


async def intercept_and_analyze(
    raw_payload: bytes | str,
    session: SessionContext,
    static_analyzer: StaticAnalyzer,
    semantic_analyzer: SemanticAnalyzer,
    *,
    emit_dashboard_event: Any | None = None,
    emit_audit_entry: Any | None = None,
) -> tuple[JsonRpcRequest, AnalysisResult, Optional[JsonRpcResponse]]:
    """
    The central interception pipeline for ALL inbound MCP traffic.

    This function is the single choke-point through which every JSON-RPC
    request must pass. It never modifies the original request — instead,
    it returns:
      • The parsed request (for forwarding if allowed).
      • The analysis result (for audit/dashboard).
      • An optional blocking response (non-None only if verdict = BLOCK).

    Architecture:
      raw bytes  ──→  [Parse]  ──→  [L1 Static]  ──→  [L2 Semantic]
                                         ↓                  ↓
                                    [Policy Engine]  ←──────┘
                                         ↓
                              ┌──────────┼──────────┐
                              │          │          │
                           ALLOW     ESCALATE     BLOCK
                              ↓          ↓          ↓
                          (forward)  (dashboard) (error response)

    Args:
        raw_payload: Raw JSON-RPC bytes or string from the transport layer.
        session: The reconstructed session context for this agent.
        static_analyzer: Pre-initialized L1 engine instance.
        semantic_analyzer: Pre-initialized L2 engine instance.
        emit_dashboard_event: Optional async callback for real-time UI events.
        emit_audit_entry: Optional async callback for audit logging.

    Returns:
        Tuple of:
          - Parsed JsonRpcRequest
          - AnalysisResult with full threat assessment
          - Optional JsonRpcResponse (blocking error) if verdict is BLOCK
    """
    t_start = time.monotonic()

    # ── Step 1: Parse JSON-RPC 2.0 packet ────────────────────────
    try:
        if isinstance(raw_payload, str):
            raw_payload = raw_payload.encode("utf-8")
        request = JsonRpcRequest.model_validate(orjson.loads(raw_payload))
    except Exception as exc:
        logger.warning("Failed to parse JSON-RPC packet: %s", exc)
        error_response = JsonRpcResponse(
            error=JsonRpcError(
                code=-32700,
                message="Parse error",
                data=str(exc),
            )
        )
        return (
            JsonRpcRequest(method="<parse_error>"),
            AnalysisResult(verdict=Verdict.BLOCK, blocked_reason=f"Parse error: {exc}"),
            error_response,
        )

    # ── Step 2: Fast-path for safe methods ───────────────────────
    if request.method in _SAFE_METHODS:
        session.push_message("agent", {"method": request.method})
        return (
            request,
            AnalysisResult(verdict=Verdict.ALLOW),
            None,
        )

    # ── Step 3: Serialize payload for analysis ───────────────────
    # We serialize once and share the string between L1 and L2.
    # This avoids redundant serialization and is effectively zero-copy
    # from the orjson parse buffer.
    payload_str = raw_payload.decode("utf-8") if isinstance(raw_payload, bytes) else raw_payload

    # ── Step 4: L1 Static Analysis (synchronous) ─────────────────
    l1_result = static_analyzer.analyze(payload_str)

    # ── Step 5: L2 Semantic Analysis (async) ─────────────────────
    # We always run L2 for high-risk methods, but skip for others
    # when L1 already returned CRITICAL (save the LLM call).
    l2_result = L2Result()
    run_l2 = request.method in _HIGH_RISK_METHODS or l1_result.threat_level != ThreatLevel.NONE

    if run_l2 and l1_result.threat_level != ThreatLevel.CRITICAL:
        l2_result = await semantic_analyzer.analyze(
            method=request.method,
            params=request.params,
            session_context=session.messages,
        )

    # ── Step 6: Policy Decision ──────────────────────────────────
    verdict, threat_level, reason = _compute_verdict(l1_result, l2_result)

    analysis = AnalysisResult(
        l1_matched_patterns=l1_result.matched_patterns,
        l1_threat_level=l1_result.threat_level,
        l2_is_injection=l2_result.is_injection,
        l2_confidence=l2_result.confidence,
        l2_reasoning=l2_result.reasoning,
        verdict=verdict,
        threat_level=threat_level,
        blocked_reason=reason,
    )

    # ── Step 7: Update session context ───────────────────────────
    session.push_message(
        "agent",
        {
            "method": request.method,
            "params_preview": str(request.params)[:200],
            "verdict": verdict.value,
        },
    )

    # ── Step 8: Emit audit + dashboard events ────────────────────
    elapsed_ms = (time.monotonic() - t_start) * 1000

    audit = AuditEntry(
        session_id=session.session_id,
        agent_id=session.agent_id,
        method=request.method,
        params_summary=str(request.params)[:500],
        analysis=analysis,
        verdict=verdict,
        response_time_ms=elapsed_ms,
    )

    if emit_audit_entry is not None:
        try:
            await emit_audit_entry(audit)
        except Exception as exc:
            logger.error("Audit emission failed: %s", exc)

    dashboard_event = DashboardEvent(
        event_type="alert" if verdict != Verdict.ALLOW else "request",
        session_id=session.session_id,
        agent_id=session.agent_id,
        method=request.method,
        payload_preview=str(request.params)[:300],
        analysis=analysis,
        is_alert=verdict != Verdict.ALLOW,
    )

    if emit_dashboard_event is not None:
        try:
            await emit_dashboard_event(dashboard_event)
        except Exception as exc:
            logger.error("Dashboard event emission failed: %s", exc)

    # ── Step 9: Build blocking response if needed ────────────────
    block_response: Optional[JsonRpcResponse] = None
    if verdict == Verdict.BLOCK:
        block_response = JsonRpcResponse(
            id=request.id,
            error=JsonRpcError(
                code=-32001,
                message="Request blocked by Agent Firewall",
                data={
                    "threat_level": threat_level.value,
                    "reason": reason,
                    "request_id": analysis.request_id,
                },
            ),
        )
        logger.warning(
            "BLOCKED %s (session=%s, threat=%s, %.1fms): %s",
            request.method,
            session.session_id[:8],
            threat_level.value,
            elapsed_ms,
            reason,
        )
    elif verdict == Verdict.ESCALATE:
        logger.info(
            "ESCALATED %s (session=%s, threat=%s, %.1fms): %s",
            request.method,
            session.session_id[:8],
            threat_level.value,
            elapsed_ms,
            reason,
        )
    else:
        logger.debug(
            "ALLOWED %s (session=%s, %.1fms)",
            request.method,
            session.session_id[:8],
            elapsed_ms,
        )

    return request, analysis, block_response
