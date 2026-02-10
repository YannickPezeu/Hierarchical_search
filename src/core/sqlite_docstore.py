# src/core/sqlite_docstore.py
"""
Convenience factory for creating a LlamaIndex KVDocumentStore
backed by SqliteKVStore.

Usage:
    from src.core.sqlite_docstore import SqliteDocumentStore

    # Create new (for indexing)
    docstore = SqliteDocumentStore.from_new(db_path)

    # Load existing (for search)
    docstore = SqliteDocumentStore.from_persist_path(db_path)
"""

import os
import logging

from llama_index.core.storage.docstore.keyval_docstore import KVDocumentStore

from src.core.sqlite_kvstore import SqliteKVStore

logger = logging.getLogger(__name__)

# Default filename for the SQLite docstore (lives alongside docstore.json)
SQLITE_DOCSTORE_FNAME = "docstore.sqlite"


class SqliteDocumentStore:
    """
    Not a class you instantiate — just a namespace for factory methods
    that produce a standard KVDocumentStore backed by SqliteKVStore.
    """

    @staticmethod
    def from_persist_path(db_path: str) -> KVDocumentStore:
        """
        Load an existing SQLite docstore from disk.

        Args:
            db_path: Full path to the .sqlite file

        Returns:
            A standard KVDocumentStore backed by SQLite
        """
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"SQLite docstore not found: {db_path}")

        kvstore = SqliteKVStore(db_path=db_path)
        logger.info(f"✅ Loaded SQLite docstore from: {db_path}")
        return KVDocumentStore(kvstore=kvstore)

    @staticmethod
    def from_new(db_path: str) -> KVDocumentStore:
        """
        Create a fresh SQLite docstore (for indexing).

        Args:
            db_path: Full path where the .sqlite file will be created

        Returns:
            A standard KVDocumentStore backed by SQLite
        """
        # Remove old file if it exists (fresh indexing)
        if os.path.exists(db_path):
            os.remove(db_path)
            logger.info(f"Removed old SQLite docstore: {db_path}")

        kvstore = SqliteKVStore(db_path=db_path)
        logger.info(f"✅ Created new SQLite docstore: {db_path}")
        return KVDocumentStore(kvstore=kvstore)

    @staticmethod
    def exists(index_dir: str) -> bool:
        """Check if a SQLite docstore exists in the given index directory."""
        return os.path.exists(os.path.join(index_dir, SQLITE_DOCSTORE_FNAME))

    @staticmethod
    def get_path(index_dir: str) -> str:
        """Get the full path to the SQLite docstore in an index directory."""
        return os.path.join(index_dir, SQLITE_DOCSTORE_FNAME)
