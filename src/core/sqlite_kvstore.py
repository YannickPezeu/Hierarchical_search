# src/core/sqlite_kvstore.py
"""
SQLite-backed Key-Value Store for LlamaIndex.

Replaces SimpleKVStore (which loads entire JSON into RAM) with a SQLite backend
that performs point lookups by primary key — sub-millisecond, zero upfront cost.

Drop-in replacement: KVDocumentStore(SqliteKVStore(...)) is API-compatible
with the default SimpleDocumentStore.
"""

import json
import logging
import os
import sqlite3
from typing import Dict, List, Optional, Tuple

from llama_index.core.storage.kvstore.types import BaseKVStore

logger = logging.getLogger(__name__)

# ── Schema ───────────────────────────────────────────────────────────────────
# One table per "collection". LlamaIndex uses 3 collections:
#   - docstore/data          (the nodes — this is the big one)
#   - docstore/ref_doc_info  (reference doc metadata)
#   - docstore/metadata      (doc-level metadata)
#
# We store them all in the same SQLite file, using the collection name
# as the table name (sanitized).
# ─────────────────────────────────────────────────────────────────────────────

def _sanitize_table_name(collection: str) -> str:
    """
    Convert a LlamaIndex collection name (e.g. 'docstore/data')
    into a valid SQLite table name (e.g. 'docstore__data').
    """
    return collection.replace("/", "__").replace("-", "_")


class SqliteKVStore(BaseKVStore):
    """
    SQLite-backed KVStore for LlamaIndex.

    Each key-value pair is stored as a row: (key TEXT PRIMARY KEY, value TEXT).
    The value is JSON-serialized.

    Thread-safety: uses check_same_thread=False and WAL mode for concurrent reads.
    """

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn = self._connect(db_path)
        logger.info(f"SqliteKVStore initialized: {db_path}")

    @staticmethod
    def _connect(db_path: str) -> sqlite3.Connection:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")       # concurrent reads
        conn.execute("PRAGMA synchronous=NORMAL")      # faster writes, still safe
        conn.execute("PRAGMA cache_size=-64000")        # 64MB page cache
        return conn

    def _ensure_table(self, collection: str) -> str:
        """Create table if needed; return sanitized table name."""
        table = _sanitize_table_name(collection)
        self._conn.execute(
            f"CREATE TABLE IF NOT EXISTS [{table}] "
            f"(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        return table

    # ── Core CRUD ────────────────────────────────────────────────────────────

    def put(self, key: str, val: dict, collection: str = "data") -> None:
        table = self._ensure_table(collection)
        self._conn.execute(
            f"INSERT OR REPLACE INTO [{table}] (key, value) VALUES (?, ?)",
            (key, json.dumps(val)),
        )
        self._conn.commit()

    async def aput(self, key: str, val: dict, collection: str = "data") -> None:
        self.put(key, val, collection)

    def put_all(
        self,
        kv_pairs: List[Tuple[str, dict]],
        collection: str = "data",
        batch_size: int = 1,
    ) -> None:
        """Batch insert — ignores batch_size, does one transaction."""
        table = self._ensure_table(collection)
        self._conn.executemany(
            f"INSERT OR REPLACE INTO [{table}] (key, value) VALUES (?, ?)",
            [(k, json.dumps(v)) for k, v in kv_pairs],
        )
        self._conn.commit()

    async def aput_all(
        self,
        kv_pairs: List[Tuple[str, dict]],
        collection: str = "data",
        batch_size: int = 1,
    ) -> None:
        self.put_all(kv_pairs, collection, batch_size)

    def get(self, key: str, collection: str = "data") -> Optional[dict]:
        table = _sanitize_table_name(collection)
        # Check if table exists first (avoids error on empty DB)
        cursor = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if cursor.fetchone() is None:
            return None

        cursor = self._conn.execute(
            f"SELECT value FROM [{table}] WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    async def aget(self, key: str, collection: str = "data") -> Optional[dict]:
        return self.get(key, collection)

    def get_all(self, collection: str = "data") -> Dict[str, dict]:
        """
        Load ALL entries. Used rarely (e.g. by load_index_from_storage for index_store).
        For the docstore/data collection this can be large — but LlamaIndex
        only calls get_all on index_store, not on docstore/data at load time.
        """
        table = _sanitize_table_name(collection)
        cursor = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if cursor.fetchone() is None:
            return {}

        cursor = self._conn.execute(f"SELECT key, value FROM [{table}]")
        return {row[0]: json.loads(row[1]) for row in cursor.fetchall()}

    async def aget_all(self, collection: str = "data") -> Dict[str, dict]:
        return self.get_all(collection)

    def delete(self, key: str, collection: str = "data") -> bool:
        table = _sanitize_table_name(collection)
        cursor = self._conn.execute(
            f"DELETE FROM [{table}] WHERE key = ?", (key,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    async def adelete(self, key: str, collection: str = "data") -> bool:
        return self.delete(key, collection)

    # ── Persistence (no-op for SQLite, it's already on disk) ─────────────────

    def persist(self, persist_path: str, **kwargs) -> None:
        """No-op. SQLite is already persisted on disk."""
        pass

    @classmethod
    def from_persist_path(cls, persist_path: str) -> "SqliteKVStore":
        """Load from an existing SQLite file."""
        if not os.path.exists(persist_path):
            raise FileNotFoundError(f"SQLite KVStore not found: {persist_path}")
        return cls(db_path=persist_path)

    # ── Utilities ────────────────────────────────────────────────────────────

    def count(self, collection: str = "data") -> int:
        """Return the number of entries in a collection."""
        table = _sanitize_table_name(collection)
        cursor = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if cursor.fetchone() is None:
            return 0
        cursor = self._conn.execute(f"SELECT COUNT(*) FROM [{table}]")
        return cursor.fetchone()[0]

    def close(self):
        """Explicitly close the connection."""
        if self._conn:
            self._conn.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def __repr__(self):
        return f"SqliteKVStore(db_path='{self._db_path}')"
