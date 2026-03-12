"""
Agent-Scan Integration Layer for Agent Firewall.

This module integrates Snyk's agent-scan security detection capabilities
into the Agent Firewall's policy engine. It provides:

1. Tool-level security analysis (Issue Codes E001-E006, W001-W013)
2. Toxic Flow detection (TF001, TF002)
3. Tool classification labels (is_public_sink, destructive, etc.)
4. Caching mechanism to avoid redundant scans

Architecture:
    Agent Firewall Interceptor
           ↓
    L1 Static Analysis (Aho-Corasick)
           ↓
    L2 Semantic Analysis (LLM)
           ↓
    Agent-Scan Analysis (this module) ← NEW
           ↓
    Policy Decision (ALLOW/BLOCK/ESCALATE)
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger("agent_firewall.agent_scan")


# ────────────────────────────────────────────────────────────────────
# Agent-Scan Models (Simplified from agent_scan.models)
# ────────────────────────────────────────────────────────────────────


class ScalarToolLabels(BaseModel):
    """Tool classification labels (0-1 float values)."""

    is_public_sink: float = 0.0  # Sends data to external/public destination
    destructive: float = 0.0  # Executes irreversible operations
    untrusted_content: float = 0.0  # Returns external/user-controlled data
    private_data: float = 0.0  # Accesses sensitive user data


class Issue(BaseModel):
    """Security issue detected by agent-scan."""

    code: str  # E001-E006 (errors), W001-W013 (warnings)
    message: str
    severity: str  # "error" | "warning"
    reference: tuple[int, int | None] | None = None  # (server_index, entity_index)
    extra_data: dict[str, Any] | None = None


class ToxicFlow(BaseModel):
    """Combination threat detected across multiple tools."""

    type: str  # "TF001" (data leak) | "TF002" (destructive)
    description: str
    tool_chain: list[str]  # Names of tools involved in the flow


@dataclass
class AgentScanResult:
    """Result from agent-scan analysis."""

    issues: list[Issue]
    labels: ScalarToolLabels
    toxic_flows: list[ToxicFlow]
    scan_time_ms: float
    cached: bool = False

    def has_critical_issues(self) -> bool:
        """Check if any critical issues (E001-E006) were detected."""
        return any(issue.code.startswith("E") for issue in self.issues)

    def has_warnings(self) -> bool:
        """Check if any warnings (W001-W013) were detected."""
        return any(issue.code.startswith("W") for issue in self.issues)

    def has_toxic_flows(self) -> bool:
        """Check if any toxic flows were detected."""
        return len(self.toxic_flows) > 0


# ────────────────────────────────────────────────────────────────────
# Agent-Scan Analyzer
# ────────────────────────────────────────────────────────────────────


class AgentScanAnalyzer:
    """
    Integrates agent-scan security analysis into Agent Firewall.

    This analyzer can operate in two modes:
    1. Local mode: Uses built-in pattern matching (fast, no API calls)
    2. Remote mode: Calls Snyk API for deep analysis (requires API key)
    """

    def __init__(
        self,
        enabled: bool = True,
        mode: str = "local",
        api_key: str = "",
        cache_ttl: int = 3600,
    ):
        self.enabled = enabled
        self.mode = mode  # "local" | "remote"
        self.api_key = api_key
        self.cache_ttl = cache_ttl
        self._cache: dict[str, tuple[AgentScanResult, float]] = {}

        if not enabled:
            logger.info("Agent-Scan integration disabled")
        else:
            logger.info(f"Agent-Scan integration enabled (mode={mode})")

    async def analyze_tool(
        self,
        tool_name: str,
        tool_description: str,
        tool_schema: dict[str, Any] | None = None,
    ) -> AgentScanResult:
        """
        Analyze a single tool for security issues.

        Args:
            tool_name: Name of the tool
            tool_description: Description text
            tool_schema: JSON schema (optional)

        Returns:
            AgentScanResult with issues, labels, and toxic flows
        """
        if not self.enabled:
            return AgentScanResult(
                issues=[],
                labels=ScalarToolLabels(),
                toxic_flows=[],
                scan_time_ms=0.0,
            )

        # Check cache
        cache_key = self._compute_cache_key(tool_name, tool_description)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result

        # Perform analysis
        start_time = time.perf_counter()

        if self.mode == "local":
            result = await self._analyze_local(tool_name, tool_description, tool_schema)
        else:
            result = await self._analyze_remote(tool_name, tool_description, tool_schema)

        scan_time_ms = (time.perf_counter() - start_time) * 1000
        result.scan_time_ms = scan_time_ms

        # Cache result
        self._set_cache(cache_key, result)

        return result

    async def _analyze_local(
        self,
        tool_name: str,
        tool_description: str,
        tool_schema: dict[str, Any] | None,
    ) -> AgentScanResult:
        """
        Local analysis using built-in pattern matching.

        This is a simplified version that checks for common security issues
        without calling external APIs.
        """
        issues: list[Issue] = []
        labels = ScalarToolLabels()

        # E001: Prompt Injection in tool description
        injection_patterns = [
            "ignore previous instructions",
            "disregard all",
            "forget everything",
            "new instructions:",
            "system:",
            "assistant:",
        ]
        desc_lower = tool_description.lower()
        for pattern in injection_patterns:
            if pattern in desc_lower:
                issues.append(
                    Issue(
                        code="E001",
                        message=f"Potential prompt injection detected: '{pattern}'",
                        severity="error",
                    )
                )
                break

        # W001: Suspicious keywords in description
        suspicious_keywords = [
            "execute",
            "shell",
            "command",
            "system",
            "eval",
            "exec",
            "subprocess",
        ]
        for keyword in suspicious_keywords:
            if keyword in desc_lower:
                issues.append(
                    Issue(
                        code="W001",
                        message=f"Suspicious keyword detected: '{keyword}'",
                        severity="warning",
                    )
                )
                break

        # W009: Direct financial execution
        financial_keywords = ["payment", "transfer", "withdraw", "purchase", "buy"]
        for keyword in financial_keywords:
            if keyword in desc_lower:
                issues.append(
                    Issue(
                        code="W009",
                        message="Direct financial execution capability detected",
                        severity="warning",
                    )
                )
                labels.destructive = 0.8
                break

        # Classify tool based on name and description
        if any(
            kw in tool_name.lower() or kw in desc_lower
            for kw in ["send", "post", "publish", "upload", "email", "slack"]
        ):
            labels.is_public_sink = 0.7

        if any(
            kw in tool_name.lower() or kw in desc_lower
            for kw in ["delete", "remove", "drop", "truncate", "destroy", "format"]
        ):
            labels.destructive = 0.9

        if any(
            kw in tool_name.lower() or kw in desc_lower
            for kw in ["fetch", "download", "scrape", "crawl", "external"]
        ):
            labels.untrusted_content = 0.6

        if any(
            kw in tool_name.lower() or kw in desc_lower
            for kw in ["password", "secret", "key", "token", "credential", "private"]
        ):
            labels.private_data = 0.8

        return AgentScanResult(
            issues=issues,
            labels=labels,
            toxic_flows=[],  # Toxic flow detection requires multiple tools
            scan_time_ms=0.0,
        )

    async def _analyze_remote(
        self,
        tool_name: str,
        tool_description: str,
        tool_schema: dict[str, Any] | None,
    ) -> AgentScanResult:
        """
        Remote analysis using Snyk API.

        This would call the actual agent-scan API for deep analysis.
        For now, falls back to local analysis.
        """
        logger.warning("Remote agent-scan mode not yet implemented, using local mode")
        return await self._analyze_local(tool_name, tool_description, tool_schema)

    def detect_toxic_flows(
        self,
        tools_with_labels: list[tuple[str, ScalarToolLabels]],
    ) -> list[ToxicFlow]:
        """
        Detect toxic flows across multiple tools.

        TF001: Data Leak Flow
            untrusted_content → private_data → is_public_sink

        TF002: Destructive Flow
            untrusted_content → destructive
        """
        if not self.enabled:
            return []

        toxic_flows: list[ToxicFlow] = []

        # Build tool index by label type
        untrusted_tools = [name for name, labels in tools_with_labels if labels.untrusted_content > 0.5]
        private_tools = [name for name, labels in tools_with_labels if labels.private_data > 0.5]
        public_sink_tools = [name for name, labels in tools_with_labels if labels.is_public_sink > 0.5]
        destructive_tools = [name for name, labels in tools_with_labels if labels.destructive > 0.5]

        # TF001: Data Leak (untrusted → private → public)
        if untrusted_tools and private_tools and public_sink_tools:
            toxic_flows.append(
                ToxicFlow(
                    type="TF001",
                    description="Data leak flow: untrusted content → private data → public sink",
                    tool_chain=[
                        untrusted_tools[0],
                        private_tools[0],
                        public_sink_tools[0],
                    ],
                )
            )

        # TF002: Destructive Flow (untrusted → destructive)
        if untrusted_tools and destructive_tools:
            toxic_flows.append(
                ToxicFlow(
                    type="TF002",
                    description="Destructive flow: untrusted content → destructive operation",
                    tool_chain=[untrusted_tools[0], destructive_tools[0]],
                )
            )

        return toxic_flows

    def _compute_cache_key(self, tool_name: str, tool_description: str) -> str:
        """Compute cache key from tool signature."""
        signature = f"{tool_name}:{tool_description}"
        return hashlib.sha256(signature.encode()).hexdigest()[:16]

    def _get_from_cache(self, cache_key: str) -> AgentScanResult | None:
        """Get cached result if not expired."""
        if cache_key in self._cache:
            result, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                result.cached = True
                return result
            else:
                del self._cache[cache_key]
        return None

    def _set_cache(self, cache_key: str, result: AgentScanResult) -> None:
        """Cache analysis result."""
        self._cache[cache_key] = (result, time.time())

    def clear_cache(self) -> None:
        """Clear all cached results."""
        self._cache.clear()
        logger.info("Agent-Scan cache cleared")
