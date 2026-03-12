"""
SQLite Storage Backend for Agent Firewall.

This is an optional storage backend that provides structured database
capabilities with SQL queries. It uses aiosqlite for async operations.

Characteristics:
- Structured schema with indexes
- Fast queries (O(log n) with indexes)
- Supports complex filters and joins
- ACID transactions
- Single-file database (easy to backup)
- No external dependencies (SQLite is built into Python)

Use cases:
- Production deployments (>10k traces/day)
- When you need complex queries
- When you need to analyze historical data
- When you need full-text search

Schema:
    traces          # Complete trace data (JSON blob + indexed fields)
    datasets        # Dataset metadata
    dataset_traces  # Many-to-many relationship
    annotations     # Annotations on traces
    policies        # Policy definitions
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import aiosqlite
except ImportError:
    aiosqlite = None  # type: ignore

from .base import StorageBackend

logger = logging.getLogger("agent_firewall.storage.sqlite")


class SqliteStorage(StorageBackend):
    """
    SQLite storage backend with structured schema.

    Database schema:
        CREATE TABLE traces (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            method TEXT,
            verdict TEXT,
            threat_level TEXT,
            data JSON,
            created_at TIMESTAMP,
            INDEX idx_session (session_id),
            INDEX idx_verdict (verdict),
            INDEX idx_threat (threat_level),
            INDEX idx_created (created_at)
        );

        CREATE TABLE datasets (
            id TEXT PRIMARY KEY,
            name TEXT,
            is_public BOOLEAN,
            metadata JSON,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );

        CREATE TABLE dataset_traces (
            dataset_id TEXT,
            trace_id TEXT,
            PRIMARY KEY (dataset_id, trace_id),
            FOREIGN KEY (dataset_id) REFERENCES datasets(id),
            FOREIGN KEY (trace_id) REFERENCES traces(id)
        );

        CREATE TABLE annotations (
            id TEXT PRIMARY KEY,
            trace_id TEXT,
            address TEXT,
            content TEXT,
            severity TEXT,
            source TEXT,
            created_at TIMESTAMP,
            FOREIGN KEY (trace_id) REFERENCES traces(id),
            INDEX idx_trace (trace_id)
        );

        CREATE TABLE policies (
            id TEXT PRIMARY KEY,
            name TEXT,
            code TEXT,
            enabled BOOLEAN,
            metadata JSON,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
    """

    def __init__(self, db_path: str = "./data/firewall.db"):
        if aiosqlite is None:
            raise ImportError(
                "aiosqlite is required for SQLite storage. "
                "Install it with: pip install aiosqlite"
            )

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db: aiosqlite.Connection | None = None

        logger.info(f"SqliteStorage initialized at {self.db_path}")

    async def _get_db(self) -> aiosqlite.Connection:
        """Get or create database connection."""
        if self._db is None:
            self._db = await aiosqlite.connect(str(self.db_path))
            self._db.row_factory = aiosqlite.Row
            await self._init_schema()
        return self._db

    async def _init_schema(self) -> None:
        """Initialize database schema."""
        db = await self._get_db()

        # Create traces table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS traces (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                method TEXT,
                verdict TEXT,
                threat_level TEXT,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("CREATE INDEX IF NOT EXISTS idx_session ON traces(session_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_verdict ON traces(verdict)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_threat ON traces(threat_level)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_created ON traces(created_at)")

        # Create datasets table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS datasets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                is_public BOOLEAN DEFAULT 0,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create dataset_traces junction table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dataset_traces (
                dataset_id TEXT,
                trace_id TEXT,
                PRIMARY KEY (dataset_id, trace_id),
                FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
                FOREIGN KEY (trace_id) REFERENCES traces(id) ON DELETE CASCADE
            )
        """)

        # Create annotations table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS annotations (
                id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL,
                address TEXT,
                content TEXT,
                severity TEXT,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trace_id) REFERENCES traces(id) ON DELETE CASCADE
            )
        """)

        await db.execute("CREATE INDEX IF NOT EXISTS idx_trace ON annotations(trace_id)")

        # Create policies table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS policies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                code TEXT,
                enabled BOOLEAN DEFAULT 1,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()
        logger.info("Database schema initialized")

    async def save_trace(self, trace: dict[str, Any]) -> str:
        """Save a trace to the database."""
        db = await self._get_db()

        trace_id = trace.get("id") or str(uuid.uuid4())
        trace["id"] = trace_id
        trace["created_at"] = trace.get("created_at") or datetime.utcnow().isoformat()

        # Extract indexed fields
        session_id = trace.get("session_id")
        method = trace.get("method")
        verdict = trace.get("analysis", {}).get("verdict")
        threat_level = trace.get("analysis", {}).get("threat_level")

        await db.execute(
            """
            INSERT INTO traces (id, session_id, method, verdict, threat_level, data, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace_id,
                session_id,
                method,
                verdict,
                threat_level,
                json.dumps(trace),
                trace["created_at"],
            ),
        )

        await db.commit()
        return trace_id

    async def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        """Retrieve a trace by ID."""
        db = await self._get_db()

        async with db.execute("SELECT data FROM traces WHERE id = ?", (trace_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return json.loads(row["data"])
            return None

    async def list_traces(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List traces with filters."""
        db = await self._get_db()

        # Build WHERE clause
        where_clauses = []
        params = []

        if filters:
            for key, value in filters.items():
                if key in ["session_id", "method", "verdict", "threat_level"]:
                    where_clauses.append(f"{key} = ?")
                    params.append(value)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Query with pagination
        query = f"""
            SELECT data FROM traces
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        traces = []
        async with db.execute(query, params) as cursor:
            async for row in cursor:
                traces.append(json.loads(row["data"]))

        return traces

    async def save_dataset(self, dataset: dict[str, Any]) -> str:
        """Save a dataset to the database."""
        db = await self._get_db()

        dataset_id = dataset.get("id") or str(uuid.uuid4())
        dataset["id"] = dataset_id
        dataset["created_at"] = dataset.get("created_at") or datetime.utcnow().isoformat()
        dataset["updated_at"] = datetime.utcnow().isoformat()

        await db.execute(
            """
            INSERT INTO datasets (id, name, is_public, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                dataset_id,
                dataset.get("name"),
                dataset.get("is_public", False),
                json.dumps(dataset.get("metadata", {})),
                dataset["created_at"],
                dataset["updated_at"],
            ),
        )

        # Add trace associations
        if "traces" in dataset:
            for trace_id in dataset["traces"]:
                await db.execute(
                    "INSERT OR IGNORE INTO dataset_traces (dataset_id, trace_id) VALUES (?, ?)",
                    (dataset_id, trace_id),
                )

        await db.commit()
        return dataset_id

    async def get_dataset(self, dataset_id: str) -> dict[str, Any] | None:
        """Retrieve a dataset by ID."""
        db = await self._get_db()

        async with db.execute(
            "SELECT * FROM datasets WHERE id = ?", (dataset_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            dataset = dict(row)
            dataset["metadata"] = json.loads(dataset["metadata"])

            # Get associated traces
            async with db.execute(
                "SELECT trace_id FROM dataset_traces WHERE dataset_id = ?",
                (dataset_id,),
            ) as trace_cursor:
                dataset["traces"] = [row["trace_id"] async for row in trace_cursor]

            return dataset

    async def list_datasets(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List datasets with filters."""
        db = await self._get_db()

        where_clauses = []
        params = []

        if filters:
            if "is_public" in filters:
                where_clauses.append("is_public = ?")
                params.append(filters["is_public"])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
            SELECT * FROM datasets
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        datasets = []
        async with db.execute(query, params) as cursor:
            async for row in cursor:
                dataset = dict(row)
                dataset["metadata"] = json.loads(dataset["metadata"])
                datasets.append(dataset)

        return datasets

    async def save_annotation(self, annotation: dict[str, Any]) -> str:
        """Save an annotation to the database."""
        db = await self._get_db()

        annotation_id = annotation.get("id") or str(uuid.uuid4())
        annotation["id"] = annotation_id
        annotation["created_at"] = annotation.get("created_at") or datetime.utcnow().isoformat()

        await db.execute(
            """
            INSERT INTO annotations (id, trace_id, address, content, severity, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                annotation_id,
                annotation.get("trace_id"),
                annotation.get("address"),
                annotation.get("content"),
                annotation.get("severity"),
                annotation.get("source"),
                annotation["created_at"],
            ),
        )

        await db.commit()
        return annotation_id

    async def get_annotations(self, trace_id: str) -> list[dict[str, Any]]:
        """Get all annotations for a trace."""
        db = await self._get_db()

        annotations = []
        async with db.execute(
            "SELECT * FROM annotations WHERE trace_id = ? ORDER BY created_at",
            (trace_id,),
        ) as cursor:
            async for row in cursor:
                annotations.append(dict(row))

        return annotations

    async def save_policy(self, policy: dict[str, Any]) -> str:
        """Save a policy to the database."""
        db = await self._get_db()

        policy_id = policy.get("id") or str(uuid.uuid4())
        policy["id"] = policy_id
        policy["created_at"] = policy.get("created_at") or datetime.utcnow().isoformat()
        policy["updated_at"] = datetime.utcnow().isoformat()

        await db.execute(
            """
            INSERT INTO policies (id, name, code, enabled, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                policy_id,
                policy.get("name"),
                policy.get("code"),
                policy.get("enabled", True),
                json.dumps(policy.get("metadata", {})),
                policy["created_at"],
                policy["updated_at"],
            ),
        )

        await db.commit()
        return policy_id

    async def get_policy(self, policy_id: str) -> dict[str, Any] | None:
        """Retrieve a policy by ID."""
        db = await self._get_db()

        async with db.execute("SELECT * FROM policies WHERE id = ?", (policy_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                policy = dict(row)
                policy["metadata"] = json.loads(policy["metadata"])
                return policy
            return None

    async def list_policies(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List policies with filters."""
        db = await self._get_db()

        where_clauses = []
        params = []

        if filters:
            if "enabled" in filters:
                where_clauses.append("enabled = ?")
                params.append(filters["enabled"])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
            SELECT * FROM policies
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        policies = []
        async with db.execute(query, params) as cursor:
            async for row in cursor:
                policy = dict(row)
                policy["metadata"] = json.loads(policy["metadata"])
                policies.append(policy)

        return policies

    async def close(self) -> None:
        """Close database connection."""
        if self._db:
            await self._db.close()
            self._db = None
            logger.info("Database connection closed")
