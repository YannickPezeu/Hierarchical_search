# src/routes/finance.py
import os
import logging
import asyncio
from typing import List

from fastapi import APIRouter, Depends, HTTPException

# Imports des modèles
from src.core.models import SearchRequest, SearchResultNode
from src.core.servicenow_models import ServiceNowLiveSearchRequest

# Imports des moteurs et composants
from src.routes.search import search_in_index, verify_internal_api_key
from src.core.servicenow_live_api import ServiceNowLiveEngine
from src.components import ApiReranker
from llama_index.core.schema import NodeWithScore, TextNode, QueryBundle

logger = logging.getLogger(__name__)
router = APIRouter()

# Instanciation du moteur Live ServiceNow
sn_engine = ServiceNowLiveEngine()

# Configuration Reranker
RERANK_API_BASE = os.getenv("RCP_API_ENDPOINT")
RERANK_API_KEY = os.getenv("RCP_API_KEY")
RERANK_MODEL = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")


@router.post("/search", response_model=List[SearchResultNode])
async def search_finance_hybrid(
        request: SearchRequest,
        _: bool = Depends(verify_internal_api_key)
):
    """
    Recherche Hybride Finance :
    1. Lex-Finance (Vectoriel local) - Top 20
    2. ServiceNow (Live API) - Top 20
    3. Fusion & Reranking global (BGE-M3) - Top 10
    """
    logger.info(f"💰 Hybrid Finance Search: '{request.query}'")

    # 1. Préparer les tâches parallèles
    # On force le rerank=False pour gagner du temps
    lex_request = SearchRequest(
        query=request.query,
        user_groups=request.user_groups,
        rerank=False,
        top_k=20
    )

    # Tâche 1 : Recherche Lex
    # Note: On appelle directement la fonction de l'autre route.
    # C'est un peu "hacky" mais ça marche car c'est une fonction async standard.
    task_lex = search_in_index(
        index_id="LEX_FR",  # Assure-toi que c'est le bon ID d'index
        request=lex_request,
        _=True  # Bypass du dependency check lors de l'appel direct
    )

    # Tâche 2 : Recherche ServiceNow
    # On utilise SERVICENOW_KB_IDS_FINANCE du .env via la logique par défaut du moteur
    task_sn = asyncio.to_thread(
        sn_engine.search,
        query=request.query,
        kb_ids=None,  # Utilisera la variable d'env par défaut (Finance)
        top_k=20
    )

    # 2. Exécution parallèle
    try:
        results_lex, results_sn = await asyncio.gather(task_lex, task_sn)
    except Exception as e:
        logger.error(f"❌ Error during parallel search: {e}")
        # En cas de crash total, on renvoie une erreur, ou on pourrait gérer un fallback partiell
        raise HTTPException(status_code=500, detail=f"Hybrid search failed: {str(e)}")

    logger.info(f"📊 Raw results: Lex={len(results_lex)}, SN={len(results_sn)}")

    # 3. Normalisation pour le Reranker (Conversion en NodeWithScore)
    nodes_to_rerank = []

    # A. Traitement Lex (ce sont déjà des SearchResultNode)
    for res in results_lex:
        # On recrée un TextNode à partir du résultat pour le reranker
        node = TextNode(
            text=res.context_content,  # On utilise le contexte large pour le reranking
            metadata={
                "title": res.title,
                "source": "LEX",
                "source_url": res.source_url,
                "original_data": res  # On garde l'objet complet pour le reconstruire après
            }
        )
        nodes_to_rerank.append(NodeWithScore(node=node, score=res.score))

    # B. Traitement ServiceNow (ServiceNowSearchResult)
    for res in results_sn:
        node = TextNode(
            text=res.content,
            metadata={
                "title": res.title,
                "source": "ServiceNow",
                "source_url": res.url,
                "original_data": res
            }
        )
        nodes_to_rerank.append(NodeWithScore(node=node, score=res.score))

    if not nodes_to_rerank:
        return []

    # 4. Global Reranking
    if RERANK_API_BASE and RERANK_API_KEY:
        reranker = ApiReranker(
            top_n=10,  # On veut le Top 10 final
            model=RERANK_MODEL,
            api_base=RERANK_API_BASE,
            api_key=RERANK_API_KEY
        )

        query_bundle = QueryBundle(query_str=request.query)
        reranked_nodes = reranker.postprocess_nodes(nodes_to_rerank, query_bundle)
        logger.info(f"🏆 Reranking complete. Kept {len(reranked_nodes)} mixed results.")
    else:
        logger.warning("⚠️ No reranker configured. Returning mixed raw results sorted by score.")
        # Fallback : trier par score brut (attention les scores Lex/SN ne sont pas comparables, mais mieux que rien)
        nodes_to_rerank.sort(key=lambda x: x.score, reverse=True)
        reranked_nodes = nodes_to_rerank[:10]

    # 5. Reformatage final en SearchResultNode
    final_results = []

    for rank, item in enumerate(reranked_nodes):
        node = item.node
        meta = node.metadata
        source_type = meta.get("source")

        if source_type == "LEX":
            # On récupère l'objet original Lex
            original: SearchResultNode = meta["original_data"]
            # On met à jour le score avec celui du reranker global
            original.score = item.score
            # Optionnel : Ajouter un préfixe au titre pour distinguer ?
            # original.title = f"[LEX] {original.title}"
            final_results.append(original)

        elif source_type == "ServiceNow":
            # On convertit le résultat SN en SearchResultNode
            original = meta["original_data"]
            final_results.append(SearchResultNode(
                title=f"[KB] {original.title}",  # Petit indicateur visuel
                precise_content=original.content,  # SN renvoie des chunks déjà, pas de distinction precise/context
                context_content=original.content,
                score=item.score,
                source_url=original.url,
                file_url=original.url,
                file_type="kb",
                node_hierarchy=f"ServiceNow > {original.kb_name}"
            ))

    return final_results