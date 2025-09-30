# src/core/utils.py
import os
from src.core.config import pwd_context, ALL_INDEXES_DIR


def get_index_path(index_id: str) -> str:
    """
    Constructs the standardized path for an index.

    Args:
        index_id: The library/index identifier

    Returns:
        Full path to the index directory
    """
    return os.path.join(ALL_INDEXES_DIR, index_id)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hashes a password."""
    return pwd_context.hash(password)