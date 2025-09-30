# src/core/models.py
from typing import List, Optional
from pydantic import BaseModel

class SearchRequest(BaseModel):
    query: str
    password: Optional[str] = None

class SearchResultNode(BaseModel):
    # ▼▼▼ MODIFIÉ ▼▼▼
    content_with_context: str   # Le contenu complet avec les paragraphes voisins
    main_content: str           # Uniquement le contenu du paragraphe principal trouvé
    # ▲▲▲ FIN DE LA MODIFICATION ▲▲▲
    score: Optional[float]
    title: str
    source_url: str
    header_path: Optional[str] = None


class IndexResponse(BaseModel):
    status: str
    message: str
    index_path: str