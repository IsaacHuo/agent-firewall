"""
JSONL Storage Backend for Agent Firewall.

This is the default, lightweight storage backend that uses append-only
JSONL (JSON Lines) files. Each line is a complete JSON object representing
a trace, dataset, annotation, or policy.

Characteristics:
- Zero dependencies (uses only Python stdlib)
- Append-only (no updates, only inserts)
- Fast writes (O(1) append)
- Slow queries (O(n) scan)
- No transactions
- File-based (easy to backup/inspect)

Use cases:
- Development and testing
- Low-volume production (<10k traces/day)
- When you need human-readable audit logs
- When you don't need complex queries
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .base import StorageBackend

logger = logging.getLogger("agent_firewall.storage.jsonl")


class JsonlStorage(StorageBackend):
    """
    JSONL storage backend using append-only log files.

    File structure:
        data/
        ├── traces.jsonl       # All traces
        ├── datasets.jsonl     # All datasets
        ├── annotations.jsonl  # All annotations
        └── policies.jsonl     # All policies
    """

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.traces_file = self.data_dir / "traces.jsonl"
        self.datasets_file = self.data_dir / "datasets.jsonl"
        self.annotations_file = self.data_dir / "annotations.jsonl"
        self.policies_file = self.data_dir / "policies.jsonl"

        # Create files if they don't exist
        for file in [self.traces_file, self.datasets_file, self.annotations_file, self.policies_file]:
            file.touch(exist_ok=True)

        logger.info(f"JsonlStorage initialized at {self.data_dir}")

    async def save_trace(self, trace: dict[str, Any]) -> str:
        """Save a trace to traces.jsonl."""
        trace_id = trace.get("id") or str(uuid.uuid4())
        trace["id"] = trace_id
        trace["created_at"] = trace.get("created_at") or datetime.now(timezone.utc).isoformat()

        await self._append_line(self.traces_file, trace)
        return trace_id

    async def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        """Retrieve a trace by ID (O(n) scan)."""
        async for line in self._read_lines(self.traces_file):
            if line.get("id") == trace_id:
                return line
        return None

    async def list_traces(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List traces with filters (O(n) scan)."""
        traces = []
        count = 0

        async for line in self._read_lines(self.traces_file):
            # Apply filters
            if filters and not self._matches_filters(line, filters):
                continue

            # Skip offset
            if count < offset:
                count += 1
                continue

            traces.append(line)

            # Stop at limit
            if len(traces) >= limit:
                break

        return traces

    async def save_dataset(self, dataset: dict[str, Any]) -> str:
        """Save a dataset to datasets.jsonl."""
        dataset_id = dataset.get("id") or str(uuid.uuid4())
        dataset["id"] = dataset_id
        dataset["created_at"] = dataset.get("created_at") or datetime.now(timezone.utc).isoformat()

        await self._append_line(self.datasets_file, dataset)
        return dataset_id

    async def get_dataset(self, dataset_id: str) -> dict[str, Any] | None:
        """Retrieve a dataset by ID."""
        async for line in self._read_lines(self.datasets_file):
            if line.get("id") == dataset_id:
                return line
        return None

    async def list_datasets(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List datasets with filters."""
        datasets = []
        count = 0

        async for line in self._read_lines(self.datasets_file):
            if filters and not self._matches_filters(line, filters):
                continue

            if count < offset:
                count += 1
                continue

            datasets.append(line)

            if len(datasets) >= limit:
                break

        return datasets

    async def save_annotation(self, annotation: dict[str, Any]) -> str:
        """Save an annotation to annotations.jsonl."""
        annotation_id = annotation.get("id") or str(uuid.uuid4())
        annotation["id"] = annotation_id
        annotation["created_at"] = annotation.get("created_at") or datetime.now(timezone.utc).isoformat()

        await self._append_line(self.annotations_file, annotation)
        return annotation_id

    async def get_annotations(self, trace_id: str) -> list[dict[str, Any]]:
        """Get all annotations for a trace."""
        annotations = []

        async for line in self._read_lines(self.annotations_file):
            if line.get("trace_id") == trace_id:
                annotations.append(line)

        return annotations

    async def save_policy(self, policy: dict[str, Any]) -> str:
        """Save a policy to policies.jsonl."""
        policy_id = policy.get("id") or str(uuid.uuid4())
        policy["id"] = policy_id
        policy["created_at"] = policy.get("created_at") or datetime.now(timezone.utc).isoformat()

        await self._append_line(self.policies_file, policy)
        return policy_id

    async def get_policy(self, policy_id: str) -> dict[str, Any] | None:
        """Retrieve a policy by ID."""
        async for line in self._read_lines(self.policies_file):
            if line.get("id") == policy_id:
                return line
        return None

    async def list_policies(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List policies with filters."""
        policies = []
        count = 0

        async for line in self._read_lines(self.policies_file):
            if filters and not self._matches_filters(line, filters):
                continue

            if count < offset:
                count += 1
                continue

            policies.append(line)

            if len(policies) >= limit:
                break

        return policies

    async def close(self) -> None:
        """No resources to close for JSONL storage."""
        pass

    # ── Helper Methods ────────────────────────────────────────────────

    async def _append_line(self, file_path: Path, data: dict[str, Any]) -> None:
        """Append a JSON line to a file (async)."""
        line = json.dumps(data, ensure_ascii=False) + "\n"

        # Use asyncio to avoid blocking
        await asyncio.to_thread(self._write_line_sync, file_path, line)

    def _write_line_sync(self, file_path: Path, line: str) -> None:
        """Synchronous write (called in thread pool)."""
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(line)

    async def _read_lines(self, file_path: Path) -> Any:
        """Read lines from a JSONL file (async generator)."""
        if not file_path.exists():
            return

        # Read file in thread pool to avoid blocking
        lines = await asyncio.to_thread(self._read_file_sync, file_path)

        for line in lines:
            line = line.strip()
            if not line:
                continue

            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse line in {file_path}: {e}")
                continue

    def _read_file_sync(self, file_path: Path) -> list[str]:
        """Synchronous file read (called in thread pool)."""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.readlines()

    def _matches_filters(self, data: dict[str, Any], filters: dict[str, Any]) -> bool:
        """Check if data matches all filters."""
        for key, value in filters.items():
            # Support nested keys (e.g., "analysis.verdict")
            if "." in key:
                parts = key.split(".")
                current = data
                for part in parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        return False

                if current != value:
                    return False
            else:
                if key not in data or data[key] != value:
                    return False

        return True
