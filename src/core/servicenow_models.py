# src/core/servicenow_models.py
from pydantic import BaseModel, Field
from typing import List, Optional

class ServiceNowIngestRequest(BaseModel):
    index_id: str
    kb_ids: List[str]
    user_groups: str

class ServiceNowLiveSearchRequest(BaseModel):
    query: str
    # Optionnel : si vide, le backend utilisera SERVICENOW_KB_IDS_FINANCE
    kb_ids: Optional[str] = None
    top_k: int = 5

class ServiceNowSearchResult(BaseModel):
    title: str
    content: str
    url: str
    kb_name: str
    score: float