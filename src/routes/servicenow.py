# src/routes/servicenow.py
import logging
import asyncio
from typing import List
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from src.core.servicenow_models import (
    ServiceNowIngestRequest,
    ServiceNowLiveSearchRequest,
    ServiceNowSearchResult
)
from src.core.servicenow_sync import servicenow_ingestion_task
from src.core.servicenow_live_api import ServiceNowLiveEngine
from src.routes.search import verify_internal_api_key

logger = logging.getLogger(__name__)
router = APIRouter()

live_engine = ServiceNowLiveEngine()

@router.post("/ingest", status_code=202)
async def trigger_servicenow_ingestion(
    request: ServiceNowIngestRequest,
    background_tasks: BackgroundTasks,
    _: bool = Depends(verify_internal_api_key)
):
    """
    Déclenche l'ingestion asynchrone (Sauvegarde fichiers MD + Indexation LlamaIndex).
    """
    if not request.kb_ids:
        raise HTTPException(status_code=400, detail="KB IDs list cannot be empty")

    background_tasks.add_task(
        servicenow_ingestion_task,
        index_id=request.index_id,
        kb_ids=request.kb_ids,
        user_groups=request.user_groups
    )

    return {"status": "Accepted", "message": "Ingestion started"}


@router.post("/live-search", response_model=List[ServiceNowSearchResult])
async def search_servicenow_live(
    request: ServiceNowLiveSearchRequest,
    _: bool = Depends(verify_internal_api_key)
):
    """
    Recherche 'Live' sur ServiceNow (sans stockage).
    Utilise les variables d'environnement pour l'auth et le modèle.
    """
    logger.info(f"🔍 Live Search ServiceNow: '{request.query}'")

    try:
        # Exécution non-bloquante
        results = await asyncio.to_thread(
            live_engine.search,
            query=request.query,
            kb_ids=request.kb_ids, # Peut être None, le moteur utilisera la défaut
            top_k=request.top_k
        )
        return results

    except ValueError as ve:
        raise HTTPException(status_code=500, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=502, detail=str(re))
    except Exception as e:
        logger.error(f"Live search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")