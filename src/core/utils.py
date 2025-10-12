# src/core/utils.py
import os
import re

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

def _normalize_text_for_comparison(text: str) -> str:
    """
    Normalisation agressive pour comparaison fuzzy.
    """
    import re
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\|', ' ', text)
    text = re.sub(r'-{3,}', ' ', text)
    text = re.sub(r'\.{4,}', ' ', text)
    text = re.sub(r'={3,}', ' ', text)
    text = text.lower()
    text = re.sub(r'[^\w\sàâäéèêëïîôùûüÿçæœ]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

