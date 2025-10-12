# src/core/models.py

from typing import List, Optional
from pydantic import BaseModel

class SearchRequest(BaseModel):
    query: str
    user_groups: List[str]
    password: Optional[str] = None


class IndexingStatus(BaseModel):
    """
    Statut de l'indexation d'une bibliothèque.
    """
    status: str  # "in_progress", "completed", "failed", "not_found"
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    failed_at: Optional[float] = None
    duration_seconds: Optional[float] = None
    num_documents: Optional[int] = None
    error: Optional[str] = None
    error_type: Optional[str] = None

class SearchResultNode(BaseModel):
    """
    Résultat de recherche avec double contenu et ancrage documentaire précis.
    """
    precise_content: str
    context_content: str
    score: Optional[float]
    title: str
    source_url: str
    header_path: Optional[str] = None
    file_url: Optional[str] = None
    file_type: Optional[str] = None
    # ✨ NOUVEAU : Fragments start/end pour text-fragment (HTML)
    search_text_start: Optional[str] = None
    search_text_end: Optional[str] = None
    # Pour navigation dans les PDFs
    node_anchor_id: Optional[str] = None
    # Pour info/debug
    page_number: Optional[int] = None
    page_confidence: Optional[float] = None
    html_confidence: Optional[float] = None
    node_hierarchy: Optional[str] = None

class IndexResponse(BaseModel):
    status: str
    message: str
    index_path: str