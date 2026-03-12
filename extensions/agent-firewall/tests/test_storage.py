"""
Tests for storage backends.

Verifies that both JSONL and SQLite storage backends correctly
implement the StorageBackend interface.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from src.storage import JsonlStorage, get_storage_backend


class TestJsonlStorage:
    """Test suite for JSONL storage backend."""

    @pytest.fixture
    async def storage(self):
        """Create a temporary JSONL storage instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonlStorage(data_dir=tmpdir)
            yield storage
            await storage.close()

    @pytest.mark.asyncio
    async def test_save_and_get_trace(self, storage):
        """Should save and retrieve a trace."""
        trace_data = {
            "session_id": "test-session",
            "method": "tools/call",
            "analysis": {
                "verdict": "ALLOW",
                "threat_level": "NONE",
            },
        }

        trace_id = await storage.save_trace(trace_data)
        assert trace_id is not None

        retrieved = await storage.get_trace(trace_id)
        assert retrieved is not None
        assert retrieved["id"] == trace_id
        assert retrieved["session_id"] == "test-session"
        assert retrieved["method"] == "tools/call"

    @pytest.mark.asyncio
    async def test_list_traces_with_filters(self, storage):
        """Should filter traces by verdict."""
        # Save multiple traces
        await storage.save_trace({
            "session_id": "s1",
            "method": "tools/call",
            "analysis": {"verdict": "ALLOW"},
        })
        await storage.save_trace({
            "session_id": "s2",
            "method": "tools/call",
            "analysis": {"verdict": "BLOCK"},
        })
        await storage.save_trace({
            "session_id": "s3",
            "method": "tools/call",
            "analysis": {"verdict": "BLOCK"},
        })

        # Filter by verdict
        blocked_traces = await storage.list_traces(
            filters={"analysis.verdict": "BLOCK"}
        )

        assert len(blocked_traces) == 2
        assert all(t["analysis"]["verdict"] == "BLOCK" for t in blocked_traces)

    @pytest.mark.asyncio
    async def test_list_traces_pagination(self, storage):
        """Should paginate trace results."""
        # Save 5 traces
        for i in range(5):
            await storage.save_trace({
                "session_id": f"s{i}",
                "method": "tools/call",
            })

        # Get first page
        page1 = await storage.list_traces(limit=2, offset=0)
        assert len(page1) == 2

        # Get second page
        page2 = await storage.list_traces(limit=2, offset=2)
        assert len(page2) == 2

        # Ensure different traces
        page1_ids = {t["id"] for t in page1}
        page2_ids = {t["id"] for t in page2}
        assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_save_and_get_dataset(self, storage):
        """Should save and retrieve a dataset."""
        dataset_data = {
            "name": "Test Dataset",
            "is_public": False,
            "traces": ["trace1", "trace2"],
        }

        dataset_id = await storage.save_dataset(dataset_data)
        assert dataset_id is not None

        retrieved = await storage.get_dataset(dataset_id)
        assert retrieved is not None
        assert retrieved["name"] == "Test Dataset"
        assert len(retrieved["traces"]) == 2

    @pytest.mark.asyncio
    async def test_save_and_get_annotations(self, storage):
        """Should save and retrieve annotations for a trace."""
        trace_id = "test-trace-123"

        # Save multiple annotations
        await storage.save_annotation({
            "trace_id": trace_id,
            "address": "messages.0.content:10-20",
            "content": "Suspicious pattern",
            "severity": "warning",
        })
        await storage.save_annotation({
            "trace_id": trace_id,
            "address": "analysis.l1_matched_patterns",
            "content": "High risk detected",
            "severity": "error",
        })

        # Retrieve annotations
        annotations = await storage.get_annotations(trace_id)
        assert len(annotations) == 2
        assert all(a["trace_id"] == trace_id for a in annotations)

    @pytest.mark.asyncio
    async def test_save_and_get_policy(self, storage):
        """Should save and retrieve a policy."""
        policy_data = {
            "name": "Block High Risk",
            "code": 'raise "High risk" if threat_level >= "HIGH"',
            "enabled": True,
        }

        policy_id = await storage.save_policy(policy_data)
        assert policy_id is not None

        retrieved = await storage.get_policy(policy_id)
        assert retrieved is not None
        assert retrieved["name"] == "Block High Risk"
        assert retrieved["enabled"] is True

    @pytest.mark.asyncio
    async def test_list_policies_with_filters(self, storage):
        """Should filter policies by enabled status."""
        await storage.save_policy({"name": "Policy 1", "enabled": True})
        await storage.save_policy({"name": "Policy 2", "enabled": False})
        await storage.save_policy({"name": "Policy 3", "enabled": True})

        enabled_policies = await storage.list_policies(
            filters={"enabled": True}
        )

        assert len(enabled_policies) == 2
        assert all(p["enabled"] is True for p in enabled_policies)


class TestSqliteStorage:
    """Test suite for SQLite storage backend."""

    @pytest.fixture
    async def storage(self):
        """Create a temporary SQLite storage instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            storage = None
            try:
                storage = get_storage_backend("sqlite", db_path=str(db_path))
                # Initialize schema
                await storage._get_db()
                yield storage
            except ImportError:
                pytest.skip("aiosqlite not installed")
            finally:
                if storage is not None:
                    await storage.close()

    @pytest.mark.asyncio
    async def test_save_and_get_trace(self, storage):
        """Should save and retrieve a trace."""
        trace_data = {
            "session_id": "test-session",
            "method": "tools/call",
            "analysis": {
                "verdict": "ALLOW",
                "threat_level": "NONE",
            },
        }

        trace_id = await storage.save_trace(trace_data)
        assert trace_id is not None

        retrieved = await storage.get_trace(trace_id)
        assert retrieved is not None
        assert retrieved["id"] == trace_id
        assert retrieved["session_id"] == "test-session"

    @pytest.mark.asyncio
    async def test_list_traces_with_indexed_filters(self, storage):
        """Should use indexes for fast filtering."""
        # Save traces with different verdicts
        await storage.save_trace({
            "session_id": "s1",
            "method": "tools/call",
            "analysis": {"verdict": "ALLOW", "threat_level": "NONE"},
        })
        await storage.save_trace({
            "session_id": "s2",
            "method": "tools/call",
            "analysis": {"verdict": "BLOCK", "threat_level": "HIGH"},
        })

        # Filter by indexed field (verdict)
        blocked = await storage.list_traces(filters={"verdict": "BLOCK"})
        assert len(blocked) == 1
        assert blocked[0]["analysis"]["verdict"] == "BLOCK"

    @pytest.mark.asyncio
    async def test_dataset_with_trace_associations(self, storage):
        """Should maintain dataset-trace relationships."""
        # Save traces
        trace1_id = await storage.save_trace({
            "session_id": "s1",
            "method": "tools/call",
        })
        trace2_id = await storage.save_trace({
            "session_id": "s2",
            "method": "tools/call",
        })

        # Save dataset with traces
        dataset_id = await storage.save_dataset({
            "name": "Test Dataset",
            "traces": [trace1_id, trace2_id],
        })

        # Retrieve dataset
        dataset = await storage.get_dataset(dataset_id)
        assert len(dataset["traces"]) == 2
        assert trace1_id in dataset["traces"]
        assert trace2_id in dataset["traces"]


class TestStorageFactory:
    """Test storage backend factory function."""

    def test_get_jsonl_backend(self):
        """Should create JSONL backend."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = get_storage_backend("jsonl", data_dir=tmpdir)
            assert isinstance(storage, JsonlStorage)

    def test_get_sqlite_backend(self):
        """Should create SQLite backend."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            try:
                storage = get_storage_backend("sqlite", db_path=str(db_path))
                assert storage is not None
            except ImportError:
                pytest.skip("aiosqlite not installed")

    def test_unknown_backend_raises_error(self):
        """Should raise error for unknown backend."""
        with pytest.raises(ValueError, match="Unknown storage backend"):
            get_storage_backend("unknown")
