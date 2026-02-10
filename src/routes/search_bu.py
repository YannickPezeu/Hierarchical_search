# src/routes/search.py - VERSION AVEC CACHE
import os
import json
import logging
from typing import List
import shutil

import faiss
from fastapi import APIRouter, HTTPException, Header, Depends
from llama_index.core import (
    StorageContext, load_index_from_storage, QueryBundle
)
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.core.schema import NodeRelationship, NodeWithScore
from llama_index.vector_stores.faiss import FaissVectorStore

from src.settings import init_settings
from src.components import ApiReranker
from src.core.config import INDEX_CACHE
from src.core.models import SearchRequest, SearchResultNode
from src.core.utils import get_index_path, verify_password
from src.core.cache import search_cache  # ✨ NOUVEAU : Import du cache
import glob

logger = logging.getLogger(__name__)
router = APIRouter()

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

if not INTERNAL_API_KEY:
    logger.warning("⚠️ INTERNAL_API_KEY not set! API will be unsecured!")


async def verify_internal_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """Vérifie que l'appel provient bien d'Open WebUI."""
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


def get_library_groups(index_id: str) -> List[str]:
    """
    Lit les groupes autorisés depuis un fichier metadata.
    Returns: Liste des group_ids autorisés, ou [] si pas de restrictions
    """
    index_path = get_index_path(index_id)
    groups_file = os.path.join(index_path, ".groups.json")

    if not os.path.exists(groups_file):
        logger.warning(
            f"No .groups.json file for library {index_id}. "
            f"This library has no group restrictions (legacy or public)."
        )
        return []

    try:
        with open(groups_file, "r") as f:
            data = json.load(f)
            groups = data.get("groups", [])
            logger.info(f"Library {index_id} authorized groups: {groups}")
            return groups
    except Exception as e:
        logger.error(f"Failed to read groups file for {index_id}: {e}")
        return []


# Ajouter cette fonction helper au début du fichier search.py
from llama_index.core.schema import NodeRelationship


def get_child_and_parent_from_subchunk(subchunk_node, docstore) -> tuple:
    """
    Remonte la hiérarchie complète depuis un sub-chunk.

    Hiérarchie: sub-chunk → child node → parent node

    Returns:
        (child_node, parent_node, hierarchy_info)
        ou (None, None, error_msg) si erreur
    """
    # Étape 1: Remonter du sub-chunk vers le child node
    if NodeRelationship.PARENT not in subchunk_node.relationships:
        return None, None, "sub-chunk has no parent (child node)"

    child_node_id = subchunk_node.relationships[NodeRelationship.PARENT].node_id
    try:
        child_node = docstore.get_node(child_node_id)
    except Exception as e:
        return None, None, f"Cannot find child node {child_node_id}: {e}"

    # Étape 2: Remonter du child node vers le parent node
    if NodeRelationship.PARENT not in child_node.relationships:
        # Le child n'a pas de parent (c'était standalone)
        # Dans ce cas, child = parent
        return child_node, child_node, "sub-chunk → child (standalone)"

    parent_node_id = child_node.relationships[NodeRelationship.PARENT].node_id
    try:
        parent_node = docstore.get_node(parent_node_id)
        return child_node, parent_node, "sub-chunk → child → parent"
    except Exception as e:
        # Fallback : utiliser child comme parent
        return child_node, child_node, f"Cannot find parent {parent_node_id}, using child: {e}"


def build_result_from_cache(
        child_node_id: str,
        parent_node_id: str,
        score: float,
        docstore,
        index_path: str
) -> SearchResultNode:
    """
    ✨ NOUVEAU : Reconstruit un SearchResultNode à partir d'IDs cachés.

    Args:
        child_node_id: ID du child node
        parent_node_id: ID du parent node
        score: Score du résultat
        docstore: Docstore pour récupérer les nodes
        index_path: Chemin de l'index

    Returns:
        SearchResultNode complet
    """
    try:
        child_node = docstore.get_node(child_node_id)
        parent_node = docstore.get_node(parent_node_id)

        precise_content = child_node.get_content()
        context_content = parent_node.get_content()

        # Construire le titre depuis file_name et header_path
        file_name = child_node.metadata.get("file_name", "Unknown")
        header_path = child_node.metadata.get("header_path", "")

        title = file_name

        # Utiliser source_filename au lieu de file_name pour le type
        source_filename = child_node.metadata.get("source_filename")

        if not source_filename:
            # Fallback : chercher dans l'archive avec le nom de base
            file_name_base = os.path.splitext(file_name)[0]
            archive_dir = os.path.join(index_path, "source_files_archive")
            pattern = os.path.join(archive_dir, "**", f"{file_name_base}.*")
            matching_files = glob.glob(pattern, recursive=True)

            exact_matches = [
                f for f in matching_files
                if os.path.splitext(os.path.basename(f))[0] == file_name_base
            ]

            if exact_matches:
                source_filename = os.path.basename(exact_matches[0])
                logger.debug(f"  Found source file via glob: {source_filename}")

        # Construire file_url et file_type depuis source_filename
        if source_filename:
            file_url = source_filename
            file_type = os.path.splitext(source_filename)[1].lower().lstrip('.')
            logger.debug(f"  file_type={file_type} from source_filename={source_filename}")
        else:
            file_url = file_name
            file_type = os.path.splitext(file_name)[1].lower().lstrip('.')
            logger.warning(f"  ⚠️ Using file_name as fallback: {file_name} → type={file_type}")

        return SearchResultNode(
            precise_content=precise_content,
            context_content=context_content,
            score=score,
            title=str(title),
            source_url=child_node.metadata.get("source_url", "URL not found"),
            header_path=child_node.metadata.get("header_path", "/"),
            file_url=file_url,
            file_type=file_type,
            search_text_start=child_node.metadata.get("search_text_start"),
            search_text_end=child_node.metadata.get("search_text_end"),
            node_anchor_id=child_node.metadata.get("node_anchor_id"),
            page_number=child_node.metadata.get("page_number"),
            page_confidence=child_node.metadata.get("page_confidence"),
            html_confidence=child_node.metadata.get("html_confidence"),
            node_hierarchy="cached"
        )

    except Exception as e:
        logger.error(f"❌ Error building result from cache: {e}")
        raise


@router.post("/{index_id}", response_model=List[SearchResultNode])
async def search_in_index(
        index_id: str,
        request: SearchRequest,
        _: bool = Depends(verify_internal_api_key)
):
    """
    Recherche avec hiérarchie à 3 niveaux + CACHE + RERANKING OPTIONNEL.

    Pipeline :
    1. Retrieval sur sub-chunks (512 tokens)
    2. Remontée vers child nodes (2000+ chars)
    3. Remontée vers parent nodes (merged, ~10k chars)
    4. Reranking sur PARENT nodes (Si request.rerank=True)
    5. Retour: precise_content (child) + context_content (parent)
    """
    logger.info(f"🔍 Search request for library: {index_id}")
    logger.info(f"👥 User groups: {request.user_groups}")
    logger.info(f"📝 Query: '{request.query}' (Rerank: {request.rerank}, Top_k: {request.top_k})")

    # ---------------------------------------------------------
    # 0. Vérifications préliminaires (Permissions & Password)
    # ---------------------------------------------------------
    library_groups = get_library_groups(index_id)
    if library_groups:
        user_group_set = set(request.user_groups)
        library_group_set = set(library_groups)
        if not user_group_set.intersection(library_group_set):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Requires groups: {library_groups}"
            )

    index_path = get_index_path(index_id)
    index_dir = os.path.join(index_path, "index")

    if not os.path.exists(index_dir):
        raise HTTPException(status_code=404, detail="Index not found")

    pw_file = os.path.join(index_path, ".pw_hash")
    if os.path.exists(pw_file):
        if not request.password:
            raise HTTPException(status_code=401, detail="Password required")
        with open(pw_file, "r") as f:
            hashed_password = f.read()
        if not verify_password(request.password, hashed_password):
            raise HTTPException(status_code=403, detail="Incorrect password")

    # ---------------------------------------------------------
    # 1. Vérification du Cache
    # ---------------------------------------------------------
    # On n'utilise le cache que si la demande de rerank correspond à ce qui est caché.
    # Pour simplifier, on invalide le cache si rerank=False (car on veut du "raw" speed)
    cached_results = None
    if request.rerank:
        cached_results = search_cache.get(
            query=request.query,
            index_id=index_id,
            index_path=index_path,
            user_groups=request.user_groups
        )

    # Chargement du VectorStore (FAISS) si nécessaire
    if index_dir not in INDEX_CACHE:
        logger.info(f"Loading index from disk: {index_dir}")
        init_settings()
        faiss_index_path = os.path.join(index_dir, "default__vector_store.json")

        if not os.path.exists(faiss_index_path):
            raise HTTPException(status_code=500, detail="FAISS index not found")

        try:
            # ON REVIENT A LA METHODE DIRECTE (MMAP sur NFS)
            # Maintenant que le fichier est intègre (5Go), cela devrait passer.
            # Le MMAP permet de ne pas charger les 5Go en RAM instantanément.
            logger.info(f"📂 Loading FAISS index directly from {faiss_index_path} with MMAP...")

            faiss_index_instance = faiss.read_index(faiss_index_path, faiss.IO_FLAG_MMAP)

            logger.info("✅ FAISS index loaded successfully (Direct MMAP).")

        except Exception as e:
            logger.error(f"❌ CRITICAL FAISS LOAD ERROR: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to load FAISS: {e}")

        vector_store = FaissVectorStore(faiss_index=faiss_index_instance)
        storage_context = StorageContext.from_defaults(
            vector_store=vector_store,
            persist_dir=index_dir
        )
        index = load_index_from_storage(storage_context)
        # On récupère large (top 50) pour avoir de la matière à reranker
        base_retriever = index.as_retriever(similarity_top_k=50)
        INDEX_CACHE[index_dir] = (base_retriever, storage_context)
    else:
        base_retriever, storage_context = INDEX_CACHE[index_dir]

    docstore = storage_context.docstore

    # Si Cache HIT : Reconstruction rapide
    if cached_results is not None:
        logger.info(f"✨ Cache HIT! Rebuilding {len(cached_results)} results")
        results = []
        for child_id, parent_id, score in cached_results:
            try:
                result = build_result_from_cache(
                    child_node_id=child_id,
                    parent_node_id=parent_id,
                    score=score,
                    docstore=docstore,
                    index_path=index_path
                )
                results.append(result)
            except Exception as e:
                logger.error(f"❌ Error rebuilding cached result: {e}")
                continue
        return results

    # ---------------------------------------------------------
    # Pipeline de Recherche (Cache MISS)
    # ---------------------------------------------------------
    logger.info(f"🔍 Cache MISS (or skipped). Running full search pipeline.")

    # ÉTAPE 1: Retrieval initial (sub-chunks)
    logger.info(f"📍 STEP 1: Retrieving sub-chunks for: '{request.query}'")
    subchunk_results = base_retriever.retrieve(request.query)
    logger.info(f"  → Retrieved {len(subchunk_results)} sub-chunks")

    # ÉTAPE 2: Remonter la hiérarchie (sub-chunk → child → parent)
    unique_child_parent_pairs = {}
    for subchunk_result in subchunk_results:
        child_node, parent_node, hierarchy_info = get_child_and_parent_from_subchunk(
            subchunk_result.node,
            docstore
        )
        if child_node is None: continue

        child_id = child_node.id_
        # On garde le meilleur score subchunk pour ce child
        if child_id in unique_child_parent_pairs:
            existing_score = unique_child_parent_pairs[child_id]['subchunk_score']
            if subchunk_result.score > existing_score:
                unique_child_parent_pairs[child_id].update({
                    'subchunk_score': subchunk_result.score,
                    'original_subchunk': subchunk_result.node
                })
        else:
            unique_child_parent_pairs[child_id] = {
                'subchunk_score': subchunk_result.score,
                'child_node': child_node,
                'parent_node': parent_node,
                'hierarchy': hierarchy_info,
                'original_subchunk': subchunk_result.node
            }

    child_parent_pairs = list(unique_child_parent_pairs.values())

    # ÉTAPE 3: Déduplication par PARENT node
    # Pour le reranking, on veut éviter de reranker 10 fois le même chapitre
    unique_parents = {}
    for pair in child_parent_pairs:
        parent_id = pair['parent_node'].id_
        if parent_id in unique_parents:
            existing_score = unique_parents[parent_id]['subchunk_score']
            if pair['subchunk_score'] > existing_score:
                unique_parents[parent_id] = pair
        else:
            unique_parents[parent_id] = pair

    deduplicated_pairs = list(unique_parents.values())
    logger.info(f"📍 STEP 3: Deduplication -> {len(deduplicated_pairs)} unique parents")

    # ÉTAPE 4: Reranking (CONDITIONNEL)
    rerank_api_base = os.getenv("RCP_API_ENDPOINT")
    rerank_api_key = os.getenv("RCP_API_KEY")
    rerank_model = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")

    # On rerank SEULEMENT si demandé ET si les clés sont là
    if request.rerank and rerank_api_base and rerank_api_key:
        logger.info(f"🚀 STEP 4: Reranking PARENT nodes with {rerank_model}")

        # Préparation des documents pour le reranker
        parent_documents = []
        temp_nodes_for_reranking = []

        for pair in deduplicated_pairs:
            parent_node = pair['parent_node']
            file_name = parent_node.metadata.get("file_name", "Unknown")
            header_path = parent_node.metadata.get("header_path", "/")
            breadcrumb = header_path.strip("/").replace("/", " > ") if header_path != "/" else "Root"

            enhanced_doc = f"[Document: {file_name} | Section: {breadcrumb}]\n\n{parent_node.get_content()}"
            parent_documents.append(enhanced_doc)

            temp_nodes_for_reranking.append(NodeWithScore(
                node=parent_node,
                score=pair['subchunk_score']
            ))

        # Appel Reranker
        reranker = ApiReranker(
            top_n=request.top_k,  # On garde le nombre demandé
            model=rerank_model,
            api_base=rerank_api_base,
            api_key=rerank_api_key,
            custom_documents=parent_documents
        )

        query_bundle = QueryBundle(query_str=request.query)
        try:
            reranked_nodes = reranker.postprocess_nodes(temp_nodes_for_reranking, query_bundle)

            # Mise à jour des scores
            final_pairs = []
            for reranked in reranked_nodes:
                for pair in deduplicated_pairs:
                    if pair['parent_node'].id_ == reranked.node.id_:
                        pair['rerank_score'] = reranked.score
                        final_pairs.append(pair)
                        break
        except Exception as e:
            logger.error(f"❌ Reranking failed: {e}. Fallback to vector scores.")
            # Fallback en cas d'erreur API
            deduplicated_pairs.sort(key=lambda x: x['subchunk_score'], reverse=True)
            for pair in deduplicated_pairs:
                pair['rerank_score'] = pair['subchunk_score']
            final_pairs = deduplicated_pairs[:request.top_k]

    else:
        # CAS SANS RERANKING (Rapide)
        logger.info(f"⏩ STEP 4: Skipped Reranking (rerank={request.rerank})")

        # Tri par score vectoriel simple
        deduplicated_pairs.sort(key=lambda x: x['subchunk_score'], reverse=True)

        # Copier le score subchunk en score final
        for pair in deduplicated_pairs:
            pair['rerank_score'] = pair['subchunk_score']

        # On coupe au Top K demandé
        final_pairs = deduplicated_pairs[:request.top_k]

    # ÉTAPE 5: Construction de la réponse
    logger.info(f"📊 STEP 5: Building {len(final_pairs)} results")
    results = []
    cache_data = []

    for pair in final_pairs:
        child_node = pair['child_node']
        parent_node = pair['parent_node']

        # Logique de métadonnées pour URL/Titre (comme avant)
        file_name = child_node.metadata.get("file_name", "Unknown")
        source_filename = child_node.metadata.get("source_filename")

        # Fallback glob si source_filename manque
        if not source_filename:
            file_name_base = os.path.splitext(file_name)[0]
            archive_dir = os.path.join(index_path, "source_files_archive")
            pattern = os.path.join(archive_dir, "**", f"{file_name_base}.*")
            matching_files = glob.glob(pattern, recursive=True)
            exact_matches = [f for f in matching_files if os.path.splitext(os.path.basename(f))[0] == file_name_base]
            if exact_matches:
                source_filename = os.path.basename(exact_matches[0])

        if source_filename:
            file_url = source_filename
            file_type = os.path.splitext(source_filename)[1].lower().lstrip('.')
        else:
            file_url = file_name
            file_type = os.path.splitext(file_name)[1].lower().lstrip('.')

        results.append(SearchResultNode(
            precise_content=child_node.get_content(),
            context_content=parent_node.get_content(),
            score=pair['rerank_score'],
            title=str(file_name),
            source_url=child_node.metadata.get("source_url", "URL not found"),
            header_path=child_node.metadata.get("header_path", "/"),
            file_url=file_url,
            file_type=file_type,
            search_text_start=child_node.metadata.get("search_text_start"),
            search_text_end=child_node.metadata.get("search_text_end"),
            node_anchor_id=child_node.metadata.get("node_anchor_id"),
            page_number=child_node.metadata.get("page_number"),
            page_confidence=child_node.metadata.get("page_confidence"),
            html_confidence=child_node.metadata.get("html_confidence"),
            node_hierarchy=pair['hierarchy']
        ))

        cache_data.append((child_node.id_, parent_node.id_, pair['rerank_score']))

    # Mise en cache (seulement si le reranking était activé, pour ne pas cacher du "low quality")
    if request.rerank:
        search_cache.set(
            query=request.query,
            index_id=index_id,
            index_path=index_path,
            user_groups=request.user_groups,
            results=cache_data
        )

    return results


@router.get("/{index_id}/cache/stats")
async def get_cache_stats(
        index_id: str,
        _: bool = Depends(verify_internal_api_key)
):
    """
    ✨ NOUVEAU : Endpoint pour obtenir les statistiques du cache.
    """
    stats = search_cache.get_stats()

    total_requests = stats["ram_hits"] + stats["disk_hits"] + stats["misses"]
    hit_rate = 0
    if total_requests > 0:
        hit_rate = ((stats["ram_hits"] + stats["disk_hits"]) / total_requests) * 100

    return {
        "cache_stats": stats,
        "total_requests": total_requests,
        "hit_rate_percentage": round(hit_rate, 2),
        "ram_cache_size": len(search_cache.ram_cache)
    }


@router.delete("/{index_id}/cache")
async def clear_index_cache(
        index_id: str,
        _: bool = Depends(verify_internal_api_key)
):
    """
    ✨ NOUVEAU : Endpoint pour vider le cache d'un index spécifique.

    Utile lors de la réindexation d'une bibliothèque.
    """
    index_path = get_index_path(index_id)
    search_cache.clear_index_cache(index_path)

    return {
        "status": "success",
        "message": f"Cache cleared for index: {index_id}"
    }