from typing import List, Optional
from pydantic import BaseModel

class SearchRequest(BaseModel):
    query: str
    user_groups: List[str]
    password: Optional[str] = None

class SearchResultNode(BaseModel):
    """
    Résultat de recherche avec double contenu:
    - precise_content: le child node exact (pour affichage à l'utilisateur)
    - context_content: le parent node avec contexte élargi (pour le LLM)
    """
    precise_content: str  # Child node - précis et ciblé
    context_content: str  # Parent node - contexte large pour le LLM
    score: Optional[float]
    title: str
    source_url: str
    header_path: Optional[str] = None
    file_url: Optional[str] = None
    file_type: Optional[str] = None
    # Optionnel: pour debug/info
    node_hierarchy: Optional[str] = None  # Ex: "sub-chunk -> child -> parent"

class IndexResponse(BaseModel):
    status: str
    message: str
    index_path: str