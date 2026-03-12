"""
Policy DSL Parser and Evaluator for Agent Firewall.

This module implements a simplified policy language for testing security policies
against traces. The DSL is inspired by Invariant's policy language but simplified
to work with Agent Firewall's existing L1/L2 analysis results.

Example policies:

    # Block high-risk requests
    raise "High risk detected" if:
        threat_level >= "HIGH"

    # Block dangerous tool calls
    raise "Dangerous tool call" if:
        tool_call.name in ["execute_code", "file_write"]

    # Block prompt injection
    raise "Prompt injection detected" if:
        l2_analysis.is_injection and l2_analysis.confidence >= 0.8

    # Complex conditions
    raise "Critical threat" if:
        threat_level == "CRITICAL" or
        (l1_patterns.count > 3 and l2_analysis.is_injection)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("agent_firewall.policy_dsl")


@dataclass
class PolicyResult:
    """Result of policy evaluation."""

    passed: bool
    message: str | None = None
    details: dict[str, Any] | None = None
    error: str | None = None


class PolicyEvaluationError(Exception):
    """Raised when policy evaluation fails."""

    pass


class PolicyEngine:
    """
    Policy DSL evaluator.

    Evaluates simplified policy expressions against trace analysis results.
    """

    def __init__(self):
        self.threat_levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    async def evaluate(
        self, policy_code: str, context: dict[str, Any]
    ) -> PolicyResult:
        """
        Evaluate a policy against a context.

        Args:
            policy_code: Policy DSL code
            context: Evaluation context with keys:
                - threat_level: str (LOW/MEDIUM/HIGH/CRITICAL)
                - l1_result: dict with patterns_found, risk_score
                - l2_result: dict with is_injection, confidence, reasoning
                - tool_calls: list of tool call dicts
                - messages: list of message dicts

        Returns:
            PolicyResult with passed=True if policy passes, False if violated
        """
        try:
            # Parse policy
            parsed = self._parse_policy(policy_code)
            if not parsed:
                return PolicyResult(
                    passed=True, message="Empty policy (always passes)"
                )

            # Evaluate condition
            condition_met = self._evaluate_condition(parsed["condition"], context)

            if condition_met:
                # Policy violated (raise statement triggered)
                return PolicyResult(
                    passed=False,
                    message=parsed["message"],
                    details={"condition": parsed["condition"], "context": context},
                )
            else:
                # Policy passed
                return PolicyResult(passed=True, message="Policy check passed")

        except Exception as e:
            logger.error(f"Policy evaluation error: {e}", exc_info=True)
            return PolicyResult(
                passed=True,  # Fail open on errors
                message="Policy evaluation error",
                error=str(e),
            )

    def _parse_policy(self, code: str) -> dict[str, Any] | None:
        """
        Parse policy DSL code.

        Supports format:
            raise "message" if:
                condition1
                condition2
        """
        code = code.strip()
        if not code:
            return None

        # Match: raise "message" if: <conditions>
        match = re.match(
            r'raise\s+"([^"]+)"\s+if:\s*(.+)', code, re.DOTALL | re.IGNORECASE
        )
        if not match:
            raise PolicyEvaluationError(
                f"Invalid policy syntax. Expected: raise \"message\" if: <condition>"
            )

        message = match.group(1)
        condition_text = match.group(2).strip()

        return {"message": message, "condition": condition_text}

    def _evaluate_condition(self, condition: str, context: dict[str, Any]) -> bool:
        """
        Evaluate a condition expression.

        Supports:
        - Comparisons: ==, !=, >=, <=, >, <
        - Logical operators: and, or, not
        - Membership: in, not in
        - Attribute access: threat_level, l2_analysis.is_injection
        - List access: tool_calls[0].name
        """
        # Normalize whitespace
        condition = " ".join(condition.split())

        # Handle logical operators (split by 'or' first, then 'and')
        if " or " in condition:
            parts = condition.split(" or ")
            return any(self._evaluate_condition(p.strip(), context) for p in parts)

        if " and " in condition:
            parts = condition.split(" and ")
            return all(self._evaluate_condition(p.strip(), context) for p in parts)

        # Handle 'not' prefix
        if condition.startswith("not "):
            rest = condition[4:].strip()
            # Check if it's "not in" (should be handled separately)
            if not rest.startswith("in "):
                return not self._evaluate_condition(rest, context)

        # Handle 'not in' operator (must come before 'in')
        if " not in " in condition:
            left, right = condition.split(" not in ", 1)
            left_val = self._resolve_value(left.strip(), context)
            right_val = self._resolve_value(right.strip(), context)
            if not isinstance(right_val, (list, tuple, set, str)):
                raise PolicyEvaluationError(
                    f"'not in' operator requires list/tuple/set/str, got {type(right_val)}"
                )
            return left_val not in right_val

        # Handle comparisons
        for op in [">=", "<=", "==", "!=", ">", "<"]:
            if f" {op} " in condition:
                left, right = condition.split(f" {op} ", 1)
                left_val = self._resolve_value(left.strip(), context)
                right_val = self._resolve_value(right.strip(), context)
                return self._compare(left_val, op, right_val)

        # Handle 'in' operator
        if " in " in condition:
            left, right = condition.split(" in ", 1)
            left_val = self._resolve_value(left.strip(), context)
            right_val = self._resolve_value(right.strip(), context)
            if not isinstance(right_val, (list, tuple, set, str)):
                raise PolicyEvaluationError(
                    f"'in' operator requires list/tuple/set/str, got {type(right_val)}"
                )
            return left_val in right_val

        # Handle boolean values directly
        val = self._resolve_value(condition, context)
        return bool(val)

    def _resolve_value(self, expr: str, context: dict[str, Any]) -> Any:
        """
        Resolve a value expression.

        Supports:
        - Literals: "string", 123, 0.5, true, false, null
        - Variables: threat_level, l1_result, l2_result
        - Attribute access: l2_result.is_injection
        - List literals: ["a", "b", "c"]
        - Nested access: tool_calls[0].function.name
        """
        expr = expr.strip()

        # String literals
        if expr.startswith('"') and expr.endswith('"'):
            return expr[1:-1]
        if expr.startswith("'") and expr.endswith("'"):
            return expr[1:-1]

        # Boolean literals
        if expr.lower() == "true":
            return True
        if expr.lower() == "false":
            return False

        # Null literal
        if expr.lower() in ("null", "none"):
            return None

        # Number literals
        try:
            if "." in expr:
                return float(expr)
            return int(expr)
        except ValueError:
            pass

        # List literals: ["a", "b", "c"]
        if expr.startswith("[") and expr.endswith("]"):
            items_str = expr[1:-1].strip()
            if not items_str:
                return []
            items = [
                item.strip() for item in items_str.split(",")
            ]  # Simple split, doesn't handle nested lists
            return [self._resolve_value(item, context) for item in items]

        # Variable/attribute access
        return self._resolve_path(expr, context)

    def _resolve_path(self, path: str, context: dict[str, Any]) -> Any:
        """
        Resolve a dotted path in context.

        Examples:
        - threat_level -> context["threat_level"]
        - l2_result.is_injection -> context["l2_result"]["is_injection"]
        - tool_calls[0].name -> context["tool_calls"][0]["name"]
        """
        parts = path.split(".")
        current = context

        for part in parts:
            # Handle list indexing: tool_calls[0]
            if "[" in part and "]" in part:
                key, index_str = part.split("[", 1)
                index_str = index_str.rstrip("]")
                try:
                    index = int(index_str)
                except ValueError:
                    raise PolicyEvaluationError(
                        f"Invalid list index: {index_str} in {path}"
                    )

                if key:
                    current = current.get(key, {})
                if isinstance(current, (list, tuple)):
                    if 0 <= index < len(current):
                        current = current[index]
                    else:
                        return None  # Index out of range
                else:
                    return None
            else:
                # Regular attribute access
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None

            if current is None:
                return None

        return current

    def _compare(self, left: Any, op: str, right: Any) -> bool:
        """Compare two values with an operator."""
        # Handle None values
        if left is None or right is None:
            if op == "==":
                return left == right
            elif op == "!=":
                return left != right
            else:
                # For other comparisons, None is treated as False
                return False

        # Special handling for threat levels
        if isinstance(left, str) and isinstance(right, str):
            if left in self.threat_levels and right in self.threat_levels:
                left_idx = self.threat_levels.index(left)
                right_idx = self.threat_levels.index(right)
                if op == ">=":
                    return left_idx >= right_idx
                elif op == "<=":
                    return left_idx <= right_idx
                elif op == ">":
                    return left_idx > right_idx
                elif op == "<":
                    return left_idx < right_idx

        # Standard comparisons
        if op == "==":
            return left == right
        elif op == "!=":
            return left != right
        elif op == ">=":
            return left >= right
        elif op == "<=":
            return left <= right
        elif op == ">":
            return left > right
        elif op == "<":
            return left < right
        else:
            raise PolicyEvaluationError(f"Unknown operator: {op}")
