# src/routes/search.py
import os
import json
import logging
from typing import List

import faiss
from fastapi import APIRouter, HTTPException, Header, Depends
from llama_index.core import (
    StorageContext, load_index_from_storage, QueryBundle
)
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.vector_stores.faiss import FaissVectorStore

from src.settings import init_settings
from src.components import ContextMerger, ApiReranker
from src.core.config import INDEX_CACHE
from src.core.models import SearchRequest, SearchResultNode
from src.core.utils import get_index_path, verify_password

logger = logging.getLogger(__name__)
router = APIRouter()

# ✅ NOUVEAU : Récupérer l'API key depuis l'environnement
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

if not INTERNAL_API_KEY:
    logger.warning("⚠️ INTERNAL_API_KEY not set! API will be unsecured!")


# ✅ NOUVEAU : Dépendance pour vérifier l'API key
async def verify_internal_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """
    Vérifie que l'appel provient bien d'Open WebUI.
    L'API key est un secret partagé entre Open WebUI et ce FastAPI.
    """
    if not INTERNAL_API_KEY:
        logger.error("INTERNAL_API_KEY not configured on server")
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: API key not set"
        )

    if x_api_key != INTERNAL_API_KEY:
        logger.warning(f"⚠️ Invalid API key attempt: {x_api_key[:10]}...")
        raise HTTPException(
            status_code=403,
            detail="Invalid API key. Only Open WebUI backend can access this endpoint."
        )

    logger.debug("✅ Valid API key - request from Open WebUI backend")
    return True


# ✅ NOUVEAU : Fonction pour récupérer les groupes autorisés d'une library
def get_library_groups(index_id: str) -> List[str]:
    """
    Lit les groupes autorisés depuis un fichier metadata.
    Ce fichier est créé lors de la création de la library.

    Returns:
        Liste des group_ids autorisés, ou [] si pas de restrictions
    """
    index_path = get_index_path(index_id)
    groups_file = os.path.join(index_path, ".groups.json")

    if not os.path.exists(groups_file):
        logger.warning(
            f"No .groups.json file for library {index_id}. "
            f"This library has no group restrictions (legacy or public)."
        )
        return []  # Pas de restrictions = accessible à tous (pour migration)

    try:
        with open(groups_file, "r") as f:
            data = json.load(f)
            groups = data.get("groups", [])
            logger.info(f"Library {index_id} authorized groups: {groups}")
            return groups
    except Exception as e:
        logger.error(f"Failed to read groups file for {index_id}: {e}")
        return []


# ✅ MODIFIÉ : Route de recherche avec vérification des groupes
@router.post("/{index_id}", response_model=List[SearchResultNode])
async def search_in_index(
        index_id: str,
        request: SearchRequest,
        _: bool = Depends(verify_internal_api_key)  # ✅ Vérifie l'API key
):
    """
    Performs a search in an existing index with group-based permissions.

    This endpoint should ONLY be called by Open WebUI backend, which:
    1. Verifies the user's JWT token
    2. Fetches the user's groups from its database
    3. Sends the verified groups in the request body

    Args:
        index_id: The library/index identifier
        request: Contains query, user_groups (verified by Open WebUI), and optional password

    Returns:
        List of search results with scores and metadata
    """
    logger.info(f"🔍 Search request for library: {index_id}")
    logger.info(f"👥 User groups (verified by Open WebUI): {request.user_groups}")

    # ✅ Vérifier les permissions basées sur les groupes
    library_groups = get_library_groups(index_id)

    if library_groups:  # Si la library a des restrictions de groupes
        user_group_set = set(request.user_groups)
        library_group_set = set(library_groups)

        # Vérifier l'intersection
        if not user_group_set.intersection(library_group_set):
            logger.warning(
                f"❌ Access denied for groups {request.user_groups} "
                f"to library {index_id} (requires: {library_groups})"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. This library requires membership in one of these groups: {library_groups}"
            )

        logger.info(f"✅ Access granted - user has required group membership")
    else:
        logger.info(f"ℹ️ Library {index_id} has no group restrictions")

    index_path = get_index_path(index_id)
    index_dir = os.path.join(index_path, "index")

    if not os.path.exists(index_dir):
        logger.error(f"❌ Index directory not found: {index_dir}")
        raise HTTPException(status_code=404, detail="Index not found.")

    # ✅ Vérification du mot de passe (optionnel, pour compatibilité)
    pw_file = os.path.join(index_path, ".pw_hash")
    if os.path.exists(pw_file):
        if not request.password:
            raise HTTPException(status_code=401, detail="Password required for this index.")
        with open(pw_file, "r") as f:
            hashed_password = f.read()
        if not verify_password(request.password, hashed_password):
            raise HTTPException(status_code=403, detail="Incorrect password.")

    # ✅ Le reste de ton code de recherche reste identique
    if index_dir not in INDEX_CACHE:
        logger.info(f"Index '{index_dir}' not in cache. Loading from FAISS...")
        init_settings()
        faiss_index_path = os.path.join(index_dir, "default__vector_store.json")
        if not os.path.exists(faiss_index_path):
            raise HTTPException(status_code=500, detail="FAISS index file not found. Please re-index.")

        try:
            faiss_index_instance = faiss.read_index(faiss_index_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load FAISS index file: {e}")

        vector_store = FaissVectorStore(faiss_index=faiss_index_instance)
        storage_context = StorageContext.from_defaults(vector_store=vector_store, persist_dir=index_dir)
        index = load_index_from_storage(storage_context)

        base_retriever = index.as_retriever(similarity_top_k=15)
        merging_retriever = AutoMergingRetriever(vector_retriever=base_retriever, storage_context=storage_context)
        INDEX_CACHE[index_dir] = (merging_retriever, storage_context)
        logger.info(f"FAISS index '{index_dir}' loaded and cached.")
    else:
        logger.info(f"Index '{index_dir}' found in cache.")
        merging_retriever, storage_context = INDEX_CACHE[index_dir]

    logger.info(f"Step 1: Initial retrieval for query: '{request.query}'")
    retrieved_nodes = merging_retriever.retrieve(request.query)
    logger.info(f"-> {len(retrieved_nodes)} nodes retrieved.")

    query_bundle = QueryBundle(query_str=request.query)
    reranked_nodes = retrieved_nodes
    rerank_api_base = os.getenv("RCP_API_ENDPOINT")
    rerank_api_key = os.getenv("RCP_API_KEY")
    rerank_model = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")

    if rerank_api_base and rerank_api_key:
        logger.info(f"Step 2: Reranking with model '{rerank_model}'...")
        documents_to_rerank = []
        for n in retrieved_nodes:
            file_name = n.node.metadata.get("file_name", "Unknown document")
            header_path = n.node.metadata.get("header_path", "/")
            breadcrumb = header_path.strip("/").replace("/", " > ") if header_path != "/" else "Root"
            enhanced_doc = f"[Document: {file_name} | Section: {breadcrumb}]\n\n{n.node.get_content()}"
            documents_to_rerank.append(enhanced_doc)

        reranker = ApiReranker(
            top_n=5,
            model=rerank_model,
            api_base=rerank_api_base,
            api_key=rerank_api_key,
            custom_documents=documents_to_rerank
        )

        reranked_nodes = reranker.postprocess_nodes(retrieved_nodes, query_bundle=query_bundle)
        logger.info(f"-> Reranking complete. {len(reranked_nodes)} nodes kept.")
    else:
        logger.warning("-> Step 2 skipped: Reranker environment variables not configured.")

    main_content_map = {n.node.node_id: n.node.get_content() for n in reranked_nodes}

    logger.info("Step 3: Merging context (adding neighbors)...")
    context_merger = ContextMerger(docstore=storage_context.docstore)
    final_nodes = context_merger.postprocess_nodes(reranked_nodes, query_bundle=query_bundle)

    results = []
    for n in final_nodes:
        title = n.node.metadata.get("Header 2", n.node.metadata.get("Header 1", n.node.metadata.get("file_name",
                                                                                                    "Title not found")))

        original_id = n.node.metadata.get('original_node_id')
        main_content = main_content_map.get(original_id, "") if original_id else "Contenu principal non trouvé"

        results.append(SearchResultNode(
            content_with_context=n.node.get_content(),
            main_content=main_content,
            score=n.score,
            title=str(title),
            source_url=n.node.metadata.get("source_url", "URL not found"),
            header_path=n.node.metadata.get("header_path", "/")
        ))

    logger.info(f"✅ Search complete. Returning {len(results)} results.")
    return results