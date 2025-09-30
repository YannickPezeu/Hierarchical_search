# src/routes/search.py
import os
import logging
from typing import List

import faiss
from fastapi import APIRouter, HTTPException
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

router = APIRouter()


@router.post("/{user_id}/{index_id}", response_model=List[SearchResultNode])
async def search_in_index(user_id: str, index_id: str, request: SearchRequest):
    """
    Performs a search in an existing index, using an in-memory cache
    and applying a reranker to improve relevance.
    """
    index_path = get_index_path(user_id, index_id)
    index_dir = os.path.join(index_path, "index")

    if not os.path.exists(index_dir):
        raise HTTPException(status_code=404, detail="Index not found.")

    pw_file = os.path.join(index_path, ".pw_hash")
    if os.path.exists(pw_file):
        if not request.password:
            raise HTTPException(status_code=401, detail="Password required for this index.")
        with open(pw_file, "r") as f:
            hashed_password = f.read()
        if not verify_password(request.password, hashed_password):
            raise HTTPException(status_code=403, detail="Incorrect password.")

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

        # Create reranker with custom documents
        reranker = ApiReranker(
            top_n=5,
            model=rerank_model,
            api_base=rerank_api_base,
            api_key=rerank_api_key,
            custom_documents=documents_to_rerank  # Pass as constructor param
        )

        # Call with standard signature
        reranked_nodes = reranker.postprocess_nodes(retrieved_nodes, query_bundle=query_bundle)
        logger.info(f"-> Reranking complete. {len(reranked_nodes)} nodes kept.")
    else:
        logger.warning("-> Step 2 skipped: Reranker environment variables not configured.")

    # ▼▼▼ NOUVEAU BLOC : Sauvegarde du contenu principal AVANT la fusion ▼▼▼
    # On crée un dictionnaire qui associe l'ID de chaque nœud à son contenu original.
    main_content_map = {n.node.node_id: n.node.get_content() for n in reranked_nodes}
    # ▲▲▲ FIN DU NOUVEAU BLOC ▲▲▲

    logger.info("Step 3: Merging context (adding neighbors)...")
    context_merger = ContextMerger(docstore=storage_context.docstore)
    final_nodes = context_merger.postprocess_nodes(reranked_nodes, query_bundle=query_bundle)


    results = []
    for n in final_nodes:
        title = n.node.metadata.get("Header 2", n.node.metadata.get("Header 1", n.node.metadata.get("file_name",
                                                                                                    "Title not found")))

        # 1. On récupère l'ID original depuis les métadonnées du noeud fusionné
        original_id = n.node.metadata.get('original_node_id')

        # 2. On utilise cet ID pour la recherche dans notre dictionnaire
        # S'il n'y a pas d'ID, on renvoie une chaîne vide ou un message d'erreur
        main_content = main_content_map.get(original_id, "") if original_id else "Contenu principal non trouvé"

        results.append(SearchResultNode(
            content_with_context=n.node.get_content(),  # Contenu fusionné (correct)
            main_content=main_content,  # Contenu original retrouvé grâce à l'ID (correct)
            score=n.score,
            title=str(title),
            source_url=n.node.metadata.get("source_url", "URL not found"),
            header_path = n.node.metadata.get("header_path", "/")

        ))

    return results