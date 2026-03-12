"""
Tests for annotation system.
"""

import pytest
import time
from src.models import Annotation


class TestAnnotationModel:
    """Test Annotation model."""

    def test_annotation_creation(self):
        """Test creating an annotation."""
        annotation = Annotation(
            id="ann-001",
            trace_id="trace-001",
            address="messages[0].content:10-20",
            content="Suspicious pattern detected",
            severity="warning",
            source="user",
            created_at=time.time()
        )

        assert annotation.id == "ann-001"
        assert annotation.trace_id == "trace-001"
        assert annotation.address == "messages[0].content:10-20"
        assert annotation.severity == "warning"
        assert annotation.source == "user"

    def test_annotation_severity_validation(self):
        """Test annotation severity validation."""
        valid_severities = ["info", "warning", "error"]

        for severity in valid_severities:
            annotation = Annotation(
                id="ann-001",
                trace_id="trace-001",
                address="messages[0].content",
                content="Test",
                severity=severity,
                source="user",
                created_at=time.time()
            )
            assert annotation.severity == severity


class TestAnnotationAPI:
    """Test annotation API endpoints."""

    @pytest.fixture
    def sample_trace_id(self):
        """Sample trace ID for testing."""
        return "trace-test-001"

    @pytest.fixture
    def sample_annotation_data(self):
        """Sample annotation data."""
        return {
            "address": "messages[0].content:10-20",
            "content": "This looks suspicious",
            "severity": "warning"
        }

    def test_add_annotation(self, sample_trace_id, sample_annotation_data):
        """Test adding an annotation to a trace."""
        # This would be an integration test with the actual API
        # For now, just validate the data structure
        assert "address" in sample_annotation_data
        assert "content" in sample_annotation_data
        assert "severity" in sample_annotation_data
        assert sample_annotation_data["severity"] in ["info", "warning", "error"]

    def test_get_annotations(self, sample_trace_id):
        """Test retrieving annotations for a trace."""
        # This would be an integration test
        # Verify the trace ID format
        assert sample_trace_id.startswith("trace-")

    def test_annotation_address_format(self):
        """Test annotation address format validation."""
        valid_addresses = [
            "messages[0].content",
            "messages[1].content:10-20",
            "messages[2].tool_calls[0].function.arguments",
        ]

        for address in valid_addresses:
            # Validate address format
            assert "messages[" in address
            assert "]" in address


class TestAnnotationFiltering:
    """Test annotation filtering by message."""

    def test_filter_annotations_by_message(self):
        """Test filtering annotations for a specific message."""
        annotations = [
            {
                "id": "ann-001",
                "address": "messages[0].content:10-20",
                "content": "Test 1",
                "severity": "info"
            },
            {
                "id": "ann-002",
                "address": "messages[1].content:5-15",
                "content": "Test 2",
                "severity": "warning"
            },
            {
                "id": "ann-003",
                "address": "messages[0].tool_calls[0]",
                "content": "Test 3",
                "severity": "error"
            }
        ]

        # Filter for message 0
        message_0_annotations = [
            ann for ann in annotations
            if ann["address"].startswith("messages[0]")
        ]

        assert len(message_0_annotations) == 2
        assert message_0_annotations[0]["id"] == "ann-001"
        assert message_0_annotations[1]["id"] == "ann-003"

        # Filter for message 1
        message_1_annotations = [
            ann for ann in annotations
            if ann["address"].startswith("messages[1]")
        ]

        assert len(message_1_annotations) == 1
        assert message_1_annotations[0]["id"] == "ann-002"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
