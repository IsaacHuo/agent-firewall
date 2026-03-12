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

# SQLite is optional (requires aiosqlite)
try:
    from .sqlite import SqliteStorage
except ImportError:
    SqliteStorage = None  # type: ignore


def get_storage_backend(
    backend_type: str = "jsonl",
    **kwargs,
) -> StorageBackend:
    """
    Factory function to create storage backend instances.

    Args:
        backend_type: "jsonl" or "sqlite"
        **kwargs: Backend-specific configuration

    Returns:
        StorageBackend instance

    Examples:
        # JSONL backend
        storage = get_storage_backend("jsonl", data_dir="./data")

        # SQLite backend
        storage = get_storage_backend("sqlite", db_path="./data/firewall.db")
    """
    if backend_type == "jsonl":
        return JsonlStorage(**kwargs)
    elif backend_type == "sqlite":
        if SqliteStorage is None:
            raise ImportError(
                "SQLite backend requires aiosqlite. "
                "Install it with: pip install aiosqlite"
            )
        return SqliteStorage(**kwargs)
    else:
        raise ValueError(f"Unknown storage backend: {backend_type}")


__all__ = [
    "StorageBackend",
    "JsonlStorage",
    "SqliteStorage",
    "get_storage_backend",
]
