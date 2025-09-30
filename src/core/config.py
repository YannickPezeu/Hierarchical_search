# src/core/config.py
from passlib.context import CryptContext

# Centralized configuration and app-wide constants
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
INDEX_CACHE = {}
ALL_INDEXES_DIR = "./all_indexes"
DOCLING_URL = "http://10.95.33.115:30842/v1/convert/file"