# src/core/utils.py
import os
from src.core.config import pwd_context, ALL_INDEXES_DIR

def get_index_path(user_id: str, index_id: str) -> str:
    """Constructs the standardized path for an index."""
    return os.path.join(ALL_INDEXES_DIR, user_id, index_id)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashes a password."""
    return pwd_context.hash(password)