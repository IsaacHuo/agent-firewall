"""
L1 Static Analyzer — High-Throughput Pattern-Based Threat Detection.

Uses a hybrid approach:
  1. **Aho-Corasick automaton** for O(n) multi-pattern matching on the full
     serialized payload. This catches known dangerous commands ("rm -rf",
     "DROP TABLE", "/etc/shadow") in a single pass regardless of pattern count.
  2. **Compiled regex battery** for structural pattern detection (Base64 blobs,
     obfuscated shell pipelines, hex-encoded payloads, common injection markers).

Design principles:
  • Zero-copy where possible — operates on bytes/memoryview.
  • Thread-safe — the automaton and compiled regexes are immutable after init.
  • Fully synchronous — L1 is CPU-bound and completes in <1ms for typical
    payloads, so we don't add async overhead here.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from typing import FrozenSet, Sequence

from ..models import ThreatLevel


# ────────────────────────────────────────────────────────────────────
# Aho-Corasick Automaton Wrapper
# ────────────────────────────────────────────────────────────────────


class AhoCorasickMatcher:
    """
    Multi-pattern string matcher using the Aho-Corasick algorithm.

    Falls back to a naive O(n*m) scan when the `ahocorasick_rs` C
    extension is unavailable (e.g., in CI without native deps).
    """

    def __init__(self, patterns: Sequence[str]) -> None:
        self._patterns = list(patterns)
        self._automaton: object | None = None

        try:
            import ahocorasick_rs  # type: ignore[import-untyped]

            self._automaton = ahocorasick_rs.AhoCorasick(self._patterns)
        except ImportError:
            # Fallback: pure-Python naive scan (acceptable for small pattern sets)
            self._automaton = None

    def find_all(self, text: str) -> list[str]:
        """Return all matched patterns found in `text`."""
        if self._automaton is not None and hasattr(self._automaton, "find_matches_as_indexes"):
            indices = self._automaton.find_matches_as_indexes(text)
            return [self._patterns[idx] for idx, _, _ in indices]

        # Fallback: brute-force scan
        return [p for p in self._patterns if p.lower() in text.lower()]


# ────────────────────────────────────────────────────────────────────
# Regex Battery — Structural Pattern Detection
# ────────────────────────────────────────────────────────────────────

# Pre-compiled regex patterns for known attack vectors.
# Each tuple: (pattern_name, compiled_regex, threat_level)

_REGEX_BATTERY: list[tuple[str, re.Pattern[str], ThreatLevel]] = [
    # Shell injection via pipes / subshells
    (
        "shell_pipe_injection",
        re.compile(
            r"(?:;|\||\$\(|`)\s*(?:bash|sh|zsh|curl|wget|nc|python|perl|ruby|node)",
            re.IGNORECASE,
        ),
        ThreatLevel.HIGH,
    ),
    # Prompt injection markers — classic "ignore previous instructions"
    (
        "prompt_injection_marker",
        re.compile(
            r"(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|prior|above)\s+"
            r"(?:instructions?|prompts?|rules?|context)",
            re.IGNORECASE,
        ),
        ThreatLevel.CRITICAL,
    ),
    # Base64-encoded payloads (>= 40 chars, likely obfuscated commands)
    (
        "base64_obfuscation",
        re.compile(r"(?:base64\s*-d|atob|b64decode)\s*[(\s]", re.IGNORECASE),
        ThreatLevel.HIGH,
    ),
    # Hex-encoded shell commands
    (
        "hex_obfuscation",
        re.compile(r"\\x[0-9a-fA-F]{2}(?:\\x[0-9a-fA-F]{2}){3,}", re.IGNORECASE),
        ThreatLevel.MEDIUM,
    ),
    # File system traversal
    (
        "path_traversal",
        re.compile(r"\.\./\.\./\.\.", re.IGNORECASE),
        ThreatLevel.HIGH,
    ),
    # Environment variable exfiltration
    (
        "env_exfiltration",
        re.compile(
            r"(?:\$\{?(?:API_KEY|SECRET|TOKEN|PASSWORD|AWS_|OPENAI_|ANTHROPIC_))",
            re.IGNORECASE,
        ),
        ThreatLevel.CRITICAL,
    ),
    # SQL injection patterns
    (
        "sql_injection",
        re.compile(
            r"(?:'\s*(?:OR|AND)\s+['\d]|UNION\s+SELECT|INTO\s+OUTFILE|LOAD_FILE)",
            re.IGNORECASE,
        ),
        ThreatLevel.HIGH,
    ),
    # Data URL exfiltration (send data to external host)
    (
        "data_exfiltration_url",
        re.compile(
            r"(?:https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
            r"https?://(?:[a-z0-9]+\.)?(?:ngrok|burpcollaborator|requestbin|webhook\.site))",
            re.IGNORECASE,
        ),
        ThreatLevel.HIGH,
    ),
    # Inline large Base64 blob (possible encoded malicious payload)
    (
        "suspicious_base64_blob",
        re.compile(r"[A-Za-z0-9+/]{60,}={0,2}", re.ASCII),
        ThreatLevel.LOW,
    ),
]


# ────────────────────────────────────────────────────────────────────
# L1 Analysis Result
# ────────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class L1Result:
    """Aggregated output from the static analysis pass."""

    matched_patterns: list[str] = field(default_factory=list)
    threat_level: ThreatLevel = ThreatLevel.NONE


# ────────────────────────────────────────────────────────────────────
# Static Analyzer Engine
# ────────────────────────────────────────────────────────────────────


class StaticAnalyzer:
    """
    L1 Static Analysis Engine.

    Combines Aho-Corasick dictionary matching with a regex battery
    to achieve both breadth (known bad strings) and depth (structural
    attack patterns) in a single pass.

    Thread-safe after construction. All mutable state lives in the
    per-call L1Result return value.
    """

    def __init__(self, blocked_commands: FrozenSet[str] | None = None) -> None:
        from ..config import FirewallConfig

        cfg = FirewallConfig()
        patterns = blocked_commands or cfg.blocked_commands
        self._blocked_commands = set(patterns)
        self._ac_matcher = AhoCorasickMatcher(list(self._blocked_commands))

    @property
    def blocked_commands(self) -> FrozenSet[str]:
        """Return the current set of blocked command patterns."""
        return frozenset(self._blocked_commands)

    def add_rule(self, pattern: str) -> None:
        """Add a new blocked command pattern and rebuild the matcher."""
        if pattern not in self._blocked_commands:
            self._blocked_commands.add(pattern)
            self._ac_matcher = AhoCorasickMatcher(list(self._blocked_commands))

    def remove_rule(self, pattern: str) -> None:
        """Remove a blocked command pattern and rebuild the matcher."""
        if pattern in self._blocked_commands:
            self._blocked_commands.discard(pattern)
            self._ac_matcher = AhoCorasickMatcher(list(self._blocked_commands))

    def analyze(self, payload: str) -> L1Result:
        """
        Run the full L1 analysis pipeline on a serialized payload string.

        Execution order:
          1. Aho-Corasick scan for blocked command fragments.
          2. Regex battery for structural pattern detection.
          3. Heuristic Base64 decode attempt on suspicious blobs.
          4. Threat-level aggregation (max of all matches).

        Returns an L1Result with all matched patterns and the highest
        threat level observed.

        Args:
            payload: The full serialized JSON-RPC payload as a string.

        Returns:
            L1Result containing matched patterns and aggregated threat level.
        """
        result = L1Result()

        # ── Phase 1: Aho-Corasick dictionary scan ────────────────────
        ac_hits = self._ac_matcher.find_all(payload)
        if ac_hits:
            result.matched_patterns.extend(f"ac:{h}" for h in ac_hits)
            result.threat_level = ThreatLevel.HIGH

        # ── Phase 2: Regex battery ───────────────────────────────────
        highest = result.threat_level
        for name, pattern, level in _REGEX_BATTERY:
            if pattern.search(payload):
                result.matched_patterns.append(f"regex:{name}")
                if _threat_ord(level) > _threat_ord(highest):
                    highest = level

        # ── Phase 3: Base64 heuristic decode ─────────────────────────
        b64_threat = self._check_base64_payloads(payload)
        if b64_threat:
            result.matched_patterns.append("heuristic:base64_decoded_threat")
            if _threat_ord(ThreatLevel.HIGH) > _threat_ord(highest):
                highest = ThreatLevel.HIGH

        result.threat_level = highest
        return result

    def _check_base64_payloads(self, text: str) -> bool:
        """
        Attempt to decode Base64 blobs and re-scan decoded content.

        This catches the attack pattern where a malicious agent encodes
        shell commands in Base64 to bypass L1 string matching:
            echo "cm0gLXJmIC8=" | base64 -d | sh
                  ^^^^^^^^^^^^^^^^^
                  This decodes to "rm -rf /"

        Only blobs >= 20 chars are candidates to avoid false positives
        on short Base64-like strings (e.g., API response IDs).

        Returns True if a threat was found in any decoded blob.
        """
        b64_pattern = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")
        for match in b64_pattern.finditer(text):
            blob = match.group()
            try:
                decoded = base64.b64decode(blob).decode("utf-8", errors="ignore")
                # Recursively check decoded content against the AC matcher only
                # (no regex to avoid infinite recursion on nested encoding)
                if self._ac_matcher.find_all(decoded):
                    return True
            except Exception:
                continue
        return False


def _threat_ord(level: ThreatLevel) -> int:
    """Map ThreatLevel to ordinal for comparison."""
    return {
        ThreatLevel.NONE: 0,
        ThreatLevel.LOW: 1,
        ThreatLevel.MEDIUM: 2,
        ThreatLevel.HIGH: 3,
        ThreatLevel.CRITICAL: 4,
    }[level]
