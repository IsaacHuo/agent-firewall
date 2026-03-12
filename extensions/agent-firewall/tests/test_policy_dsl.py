"""
Tests for Policy DSL Parser and Evaluator.
"""

import pytest
from src.engine.policy_dsl import PolicyEngine, PolicyEvaluationError, PolicyResult


@pytest.mark.asyncio
class TestPolicyEngine:
    """Test policy DSL evaluation."""

    async def test_empty_policy(self):
        """Empty policy should pass."""
        engine = PolicyEngine()
        result = await engine.evaluate("", {})
        assert result.passed is True

    async def test_threat_level_comparison(self):
        """Test threat level comparisons."""
        engine = PolicyEngine()

        # HIGH >= HIGH should trigger
        policy = 'raise "High risk" if: threat_level >= "HIGH"'
        result = await engine.evaluate(policy, {"threat_level": "HIGH"})
        assert result.passed is False
        assert "High risk" in result.message

        # MEDIUM >= HIGH should not trigger
        result = await engine.evaluate(policy, {"threat_level": "MEDIUM"})
        assert result.passed is True

        # CRITICAL >= HIGH should trigger
        result = await engine.evaluate(policy, {"threat_level": "CRITICAL"})
        assert result.passed is False

    async def test_tool_call_name_check(self):
        """Test tool call name checking."""
        engine = PolicyEngine()
        policy = 'raise "Dangerous tool" if: tool_calls[0].function.name in ["execute_code", "file_write"]'

        # Should trigger for execute_code
        context = {
            "tool_calls": [{"function": {"name": "execute_code", "arguments": {}}}]
        }
        result = await engine.evaluate(policy, context)
        assert result.passed is False
        assert "Dangerous tool" in result.message

        # Should not trigger for safe_read
        context = {"tool_calls": [{"function": {"name": "safe_read", "arguments": {}}}]}
        result = await engine.evaluate(policy, context)
        assert result.passed is True

    async def test_l2_analysis_check(self):
        """Test L2 analysis result checking."""
        engine = PolicyEngine()
        policy = 'raise "Injection detected" if: l2_result.is_injection and l2_result.confidence >= 0.8'

        # Should trigger when both conditions met
        context = {"l2_result": {"is_injection": True, "confidence": 0.9}}
        result = await engine.evaluate(policy, context)
        assert result.passed is False

        # Should not trigger when confidence too low
        context = {"l2_result": {"is_injection": True, "confidence": 0.5}}
        result = await engine.evaluate(policy, context)
        assert result.passed is True

        # Should not trigger when not injection
        context = {"l2_result": {"is_injection": False, "confidence": 0.9}}
        result = await engine.evaluate(policy, context)
        assert result.passed is True

    async def test_complex_conditions(self):
        """Test complex logical conditions."""
        engine = PolicyEngine()

        # Test simple OR condition
        policy = 'raise "Critical" if: threat_level == "CRITICAL"'
        context = {"threat_level": "CRITICAL"}
        result = await engine.evaluate(policy, context)
        assert result.passed is False

        # Test AND condition without parentheses
        policy = 'raise "High risk injection" if: l1_result.risk_score > 0.5 and l2_result.is_injection'
        context = {
            "l1_result": {"risk_score": 0.7},
            "l2_result": {"is_injection": True},
        }
        result = await engine.evaluate(policy, context)
        assert result.passed is False

        # Should not trigger when one condition fails
        context = {
            "l1_result": {"risk_score": 0.3},
            "l2_result": {"is_injection": True},
        }
        result = await engine.evaluate(policy, context)
        assert result.passed is True

    async def test_list_literals(self):
        """Test list literal parsing."""
        engine = PolicyEngine()
        policy = 'raise "Bad tool" if: tool_calls[0].function.name in ["exec", "eval", "compile"]'

        context = {"tool_calls": [{"function": {"name": "eval", "arguments": {}}}]}
        result = await engine.evaluate(policy, context)
        assert result.passed is False

    async def test_not_operator(self):
        """Test NOT operator."""
        engine = PolicyEngine()
        policy = 'raise "Not allowed" if: not l2_result.is_safe'

        context = {"l2_result": {"is_safe": False}}
        result = await engine.evaluate(policy, context)
        assert result.passed is False

        context = {"l2_result": {"is_safe": True}}
        result = await engine.evaluate(policy, context)
        assert result.passed is True

    async def test_missing_fields(self):
        """Test handling of missing fields."""
        engine = PolicyEngine()
        policy = 'raise "Error" if: nonexistent.field == "value"'

        # Should not crash, should pass (None != "value")
        result = await engine.evaluate(policy, {})
        assert result.passed is True

    async def test_invalid_syntax(self):
        """Test invalid policy syntax."""
        engine = PolicyEngine()
        policy = "this is not valid syntax"

        result = await engine.evaluate(policy, {})
        # Should fail open (pass) on syntax errors
        assert result.passed is True
        assert result.error is not None

    async def test_string_literals(self):
        """Test string literal parsing."""
        engine = PolicyEngine()
        policy = 'raise "Match" if: verdict == "BLOCK"'

        context = {"verdict": "BLOCK"}
        result = await engine.evaluate(policy, context)
        assert result.passed is False

        context = {"verdict": "ALLOW"}
        result = await engine.evaluate(policy, context)
        assert result.passed is True

    async def test_numeric_comparisons(self):
        """Test numeric comparisons."""
        engine = PolicyEngine()
        policy = 'raise "High confidence" if: l2_result.confidence > 0.8'

        context = {"l2_result": {"confidence": 0.9}}
        result = await engine.evaluate(policy, context)
        assert result.passed is False

        context = {"l2_result": {"confidence": 0.5}}
        result = await engine.evaluate(policy, context)
        assert result.passed is True

    async def test_not_in_operator(self):
        """Test NOT IN operator."""
        engine = PolicyEngine()
        policy = 'raise "Unsafe tool" if: tool_calls[0].function.name not in ["read_file", "list_files"]'

        context = {"tool_calls": [{"function": {"name": "execute_code", "arguments": {}}}]}
        result = await engine.evaluate(policy, context)
        assert result.passed is False

        context = {"tool_calls": [{"function": {"name": "read_file", "arguments": {}}}]}
        result = await engine.evaluate(policy, context)
        assert result.passed is True
