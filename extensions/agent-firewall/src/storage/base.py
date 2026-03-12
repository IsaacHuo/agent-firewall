"""
Storage Backend Abstraction Layer for Agent Firewall.

This module provides a unified interface for different storage backends:
- JSONL: Lightweight, append-only log files (default)
- SQLite: Structured database with query capabilities (optional)

Architecture:
    StorageBackend (ABC)
         ↓
    ┌────┴────┐
    │         │
 JsonlStorage  SqliteStorage
    │         │
    └────┬────┘
         ↓
    Used by: Audit Logger, Trace Manager, Dataset Manager
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class StorageBackend(ABC):
    """
    Abstract base class for storage backends.

    All storage implementations must provide these core operations:
    - save_trace: Store a complete trace (request + analysis + response)
    - get_trace: Retrieve a trace by ID
    - list_traces: Query traces with filters
    - save_dataset: Store a dataset (collection of traces)
    - get_dataset: Retrieve a dataset by ID
    - list_datasets: Query datasets with filters
    """

    @abstractmethod
    async def save_trace(self, trace: dict[str, Any]) -> str:
        """
        Save a trace to storage.

        Args:
            trace: Trace data (see Trace model in models.py)

        Returns:
            trace_id: Unique identifier for the saved trace
        """
        pass

    @abstractmethod
    async def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        """
        Retrieve a trace by ID.

        Args:
            trace_id: Unique trace identifier

        Returns:
            Trace data or None if not found
        """
        pass

    @abstractmethod
    async def list_traces(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        List traces with optional filters.

        Args:
            filters: Query filters (e.g., {"verdict": "BLOCK", "threat_level": "HIGH"})
            limit: Maximum number of traces to return
            offset: Number of traces to skip (pagination)

        Returns:
            List of trace data
        """
        pass

    @abstractmethod
    async def save_dataset(self, dataset: dict[str, Any]) -> str:
        """
        Save a dataset to storage.

        Args:
            dataset: Dataset data (see Dataset model in models.py)

        Returns:
            dataset_id: Unique identifier for the saved dataset
        """
        pass

    @abstractmethod
    async def get_dataset(self, dataset_id: str) -> dict[str, Any] | None:
        """
        Retrieve a dataset by ID.

        Args:
            dataset_id: Unique dataset identifier

        Returns:
            Dataset data or None if not found
        """
        pass

    @abstractmethod
    async def list_datasets(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        List datasets with optional filters.

        Args:
            filters: Query filters
            limit: Maximum number of datasets to return
            offset: Number of datasets to skip (pagination)

        Returns:
            List of dataset data
        """
        pass

    @abstractmethod
    async def save_annotation(self, annotation: dict[str, Any]) -> str:
        """
        Save an annotation to storage.

        Args:
            annotation: Annotation data (see Annotation model in models.py)

        Returns:
            annotation_id: Unique identifier for the saved annotation
        """
        pass

    @abstractmethod
    async def get_annotations(
        self,
        trace_id: str,
    ) -> list[dict[str, Any]]:
        """
        Get all annotations for a trace.

        Args:
            trace_id: Trace identifier

        Returns:
            List of annotation data
        """
        pass

    @abstractmethod
    async def save_policy(self, policy: dict[str, Any]) -> str:
        """
        Save a policy to storage.

        Args:
            policy: Policy data (see Policy model in models.py)

        Returns:
            policy_id: Unique identifier for the saved policy
        """
        pass

    @abstractmethod
    async def get_policy(self, policy_id: str) -> dict[str, Any] | None:
        """
        Retrieve a policy by ID.

        Args:
            policy_id: Unique policy identifier

        Returns:
            Policy data or None if not found
        """
        pass

    @abstractmethod
    async def list_policies(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        List policies with optional filters.

        Args:
            filters: Query filters
            limit: Maximum number of policies to return
            offset: Number of policies to skip (pagination)

        Returns:
            List of policy data
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close storage backend and release resources."""
        pass
