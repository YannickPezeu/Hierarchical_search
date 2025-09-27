# src/main.py (VERSION FINALE AVEC UNSTRUCTURED)
import os
import json
import logging
import shutil
from typing import List, Optional
from collections import Counter

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
from passlib.context import CryptContext

# --- Imports de notre logique RAG ---
from llama_index.core import StorageContext, load_index_from_storage, VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo
from llama_index.core.ingestion import IngestionPipeline

from src.settings import init_settings
from src.components import FilterEmptyNodes, RepairRelationships, AddBreadcrumbs, ContextMerger, CleanHeaders # <--- AJOUTER CleanHeaders
from unstructured.partition.pdf import partition_pdf
from unstructured.staging.base import elements_to_markdown # <--- LE BON CHEMIN POUR VOTRE VERSION

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="API de Recherche Sémantique")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

INDEX_CACHE = {}
ALL_INDEXES_DIR = "./all_indexes"


# --- Modèles de données Pydantic (inchangés) ---
class SearchRequest(BaseModel):
    query: str
    password: Optional[str] = None


class SearchResultNode(BaseModel):
    content: str
    score: Optional[float]
    title: str
    source_url: str


class IndexResponse(BaseModel):
    status: str
    message: str
    index_path: str


# --- Fonctions Helpers (nettoyées) ---
def get_index_path(user_id: str, index_id: str) -> str:
    return os.path.join(ALL_INDEXES_DIR, user_id, index_id)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)





# --- Logique d'indexation (entièrement retravaillée) ---

# src/main.py (remplacez l'ancienne fonction run_indexing_logic par celle-ci)

# src/main.py (remplacez votre fonction run_indexing_logic par celle-ci)

def run_indexing_logic(source_dir: str, index_dir: str, metadata: dict):
    """
    Logique d'ingestion LlamaIndex utilisant un pipeline complet,
    y compris le nettoyage des documents après lecture.
    """
    logger.info(f"Démarrage de l'indexation LlamaIndex pour le dossier : {source_dir}")
    init_settings()

    # --- DÉFINITION DE LA FONCTION MANQUANTE ---
    def get_file_metadata(file_path: str) -> dict:
        """Crée le dictionnaire de métadonnées pour un fichier donné."""
        filename = os.path.basename(file_path)
        return {"source_url": metadata.get(filename, "URL non fournie")}

    # --- FIN DE LA DÉFINITION ---

    # Étape 1: Lecture des documents (un par page)
    # L'appel à `file_metadata=get_file_metadata` va maintenant fonctionner
    reader = SimpleDirectoryReader(input_dir=source_dir, file_metadata=get_file_metadata)
    documents_par_page = reader.load_data(show_progress=True)
    logger.info(f"{len(documents_par_page)} pages chargées depuis la source.")

    # Étape 2: Regrouper le contenu et sauvegarder le .md pour vérification
    md_files_dir = os.path.join(os.path.dirname(source_dir), "md_files")
    os.makedirs(md_files_dir, exist_ok=True)

    if documents_par_page:
        full_text_content = "\n\n".join([doc.text for doc in documents_par_page])
        original_filename = os.path.basename(documents_par_page[0].metadata.get('file_name', 'document.pdf'))
        md_filename = f"{os.path.splitext(original_filename)[0]}.md"

        logger.info(f"Sauvegarde du fichier .md complet pour vérification : {md_filename}")
        with open(os.path.join(md_files_dir, md_filename), "w", encoding="utf-8") as f:
            f.write(full_text_content)

    # Étape 3: Définition du pipeline de transformation
    pipeline = IngestionPipeline(
        transformations=[
            CleanHeaders(),
            MarkdownNodeParser(include_metadata=True, include_prev_next_rel=True),
            FilterEmptyNodes(min_length=30, min_lines=3),
            RepairRelationships(),
        ]
    )

    # Étape 4: Exécution du pipeline
    parent_nodes = pipeline.run(documents=documents_par_page)

    # Étape 5: Création des enfants et de l'index
    child_splitter = SentenceSplitter(chunk_size=128, chunk_overlap=0)
    all_nodes = []
    child_nodes = []
    for parent_node in parent_nodes:
        sub_nodes = child_splitter.get_nodes_from_documents([parent_node])
        for sub_node in sub_nodes:
            sub_node.relationships[NodeRelationship.PARENT] = RelatedNodeInfo(node_id=parent_node.id_)
            child_nodes.append(sub_node)
        all_nodes.append(parent_node)
        all_nodes.extend(sub_nodes)

    storage_context = StorageContext.from_defaults()
    storage_context.docstore.add_documents(all_nodes)
    index = VectorStoreIndex(nodes=child_nodes, storage_context=storage_context)
    index.storage_context.persist(persist_dir=index_dir)
    logger.info(f"Indexation terminée et sauvegardée dans : {index_dir}")

def index_creation_task(user_id: str, index_id: str, metadata_json: str):
    """Tâche de fond simplifiée : lance juste l'indexation sur le dossier source."""
    index_path = get_index_path(user_id, index_id)
    source_files_dir = os.path.join(index_path, "source_files")
    index_dir = os.path.join(index_path, "index")

    try:
        metadata = json.loads(metadata_json)
        run_indexing_logic(source_dir=source_files_dir, index_dir=index_dir, metadata=metadata)
    except Exception as e:
        logger.error(f"Erreur lors de la tâche d'indexation pour '{index_path}': {e}", exc_info=True)
        shutil.rmtree(index_path)


# --- Routes de l'API (seule /index est modifiée) ---

@app.post("/index/{user_id}/{index_id}", status_code=status.HTTP_202_ACCEPTED, response_model=IndexResponse)
async def create_index(
        user_id: str,
        index_id: str,
        background_tasks: BackgroundTasks,
        files: List[UploadFile] = File(...),
        metadata_json: str = Form(...),
        password: Optional[str] = Form(None)
):
    index_path = get_index_path(user_id, index_id)
    source_files_dir = os.path.join(index_path, "source_files")

    if os.path.exists(index_path):
        logger.info(f"L'index '{index_id}' existe déjà. Nettoyage des anciens fichiers générés...")
        for sub in ["md_files", "index",
                    ".pw_hash"]:  # md_files n'est plus utilisé mais on le garde pour nettoyer les anciennes versions
            path_to_remove = os.path.join(index_path, sub)
            if os.path.exists(path_to_remove):
                if os.path.isdir(path_to_remove):
                    shutil.rmtree(path_to_remove)
                else:
                    os.remove(path_to_remove)

    os.makedirs(source_files_dir, exist_ok=True)

    for file in files:
        file_path = os.path.join(source_files_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    if password:
        hashed_password = get_password_hash(password)
        with open(os.path.join(index_path, ".pw_hash"), "w") as f:
            f.write(hashed_password)

    # La tâche de fond est maintenant beaucoup plus simple
    background_tasks.add_task(index_creation_task, user_id, index_id, metadata_json)

    return {"status": "Accepted", "message": "Les fichiers ont été sauvegardés. L'indexation directe a démarré.",
            "index_path": index_path}


@app.post("/search/{user_id}/{index_id}", response_model=List[SearchResultNode])
async def search_in_index(user_id: str, index_id: str, request: SearchRequest):
    """
    Effectue une recherche dans un index existant, en utilisant un cache en mémoire.
    """
    index_path = get_index_path(user_id, index_id)
    index_dir = os.path.join(index_path, "index")

    if not os.path.exists(index_dir):
        raise HTTPException(status_code=404, detail="Index non trouvé.")

    # Vérification du mot de passe (inchangé)
    pw_file = os.path.join(index_path, ".pw_hash")
    if os.path.exists(pw_file):
        if not request.password:
            raise HTTPException(status_code=401, detail="Mot de passe requis pour cet index.")
        with open(pw_file, "r") as f:
            hashed_password = f.read()
        if not verify_password(request.password, hashed_password):
            raise HTTPException(status_code=403, detail="Mot de passe incorrect.")

    # --- LOGIQUE DE CACHING ---
    if index_dir not in INDEX_CACHE:
        logger.info(f"Index '{index_dir}' non trouvé dans le cache. Chargement...")
        init_settings()
        storage_context = StorageContext.from_defaults(persist_dir=index_dir)
        index = load_index_from_storage(storage_context)

        base_retriever = index.as_retriever(similarity_top_k=5)
        merging_retriever = AutoMergingRetriever(
            vector_retriever=base_retriever,
            storage_context=storage_context,
        )
        INDEX_CACHE[index_dir] = (merging_retriever, storage_context)  # On met aussi le context en cache
        logger.info(f"Index '{index_dir}' chargé et mis en cache.")
    else:
        logger.info(f"Index '{index_dir}' trouvé dans le cache.")
        merging_retriever, storage_context = INDEX_CACHE[index_dir]  # On récupère les deux

    # La suite de la logique utilise le retriever (chargé ou depuis le cache)
    query_engine = RetrieverQueryEngine.from_args(
        retriever=merging_retriever,
        node_postprocessors=[
            # On utilise directement la variable storage_context locale
            ContextMerger(docstore=storage_context.docstore),
            AddBreadcrumbs()
        ]
    )

    retrieved_nodes = query_engine.retrieve(request.query)

    # Formatter la réponse
    results = []
    for n in retrieved_nodes:
        title = n.node.metadata.get("Header 2", n.node.metadata.get("Header 1", "Titre non trouvé"))
        results.append(SearchResultNode(
            content=n.node.get_content(),
            score=n.score,
            title=str(title),
            source_url=n.node.metadata.get("source_url", "URL non trouvée")
        ))

    return results