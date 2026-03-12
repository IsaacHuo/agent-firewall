"""
Storage module for Agent Firewall.

Provides unified storage abstraction with multiple backends:
- JSONL: Lightweight, append-only (default)
- SQLite: Structured database (optional)

Usage:
    from src.storage import get_storage_backend

    # Get default backend (JSONL)
    storage = get_storage_backend()

    # Get SQLite backend
    storage = get_storage_backend("sqlite", db_path="./data/firewall.db")

    # Save a trace
    trace_id = await storage.save_trace(trace_data)

    # Query traces
    traces = await storage.list_traces(
        filters={"verdict": "BLOCK"},
        limit=10
    )
"""

from .base import StorageBackend
from .jsonl import JsonlStorage


def get_storage_backend(
    backend: str = "jsonl",
    path: str = "./data",
    **kwargs,
) -> StorageBackend:
    """
    Factory function to create storage backend instances.

    Args:
        backend: "jsonl"
        path: Path to storage (directory for jsonl)
        **kwargs: Backend-specific configuration

    Returns:
        StorageBackend instance

    Examples:
        # JSONL backend
        storage = get_storage_backend("jsonl", path="./data")
    """
    if backend == "jsonl":
        return JsonlStorage(data_dir=path, **kwargs)
    else:
        # Fallback to jsonl for now if unknown, or raise error?
        # Given "no more sqlite", treating anything else as error or default to jsonl seems fine.
        # But let's stick to the current pattern but remove sqlite branch.
        raise ValueError(f"Unknown storage backend: {backend}. Only 'jsonl' is supported.")


__all__ = [
    "StorageBackend",
    "JsonlStorage",
    "get_storage_backend",
]
