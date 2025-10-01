# src/core/models.py
from typing import List, Optional
from pydantic import BaseModel

class SearchRequest(BaseModel):
    query: str
    user_groups: List[str]  # ✅ NOUVEAU : Groupes vérifiés par Open WebUI
    password: Optional[str] = None

class SearchResultNode(BaseModel):
    content_with_context: str
    main_content: str
    score: Optional[float]
    title: str
    source_url: str
    header_path: Optional[str] = None
    file_url: Optional[str] = None  # Ex: "/files/lib123/document.pdf"
    file_type: Optional[str] = None  # Ex: "pdf", "docx", "html"

class IndexResponse(BaseModel):
    status: str
    message: str
    index_path: str