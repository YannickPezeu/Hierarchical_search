# src/main.py
import os
import json
import logging
import shutil
from typing import List, Optional

import requests
from pydantic import BaseModel
from passlib.context import CryptContext



from src.settings import init_settings
from src.components import FilterEmptyNodes, RepairRelationships, AddBreadcrumbs, ContextMerger
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException, status


# --- Imports de notre logique RAG ---
from llama_index.core import StorageContext, load_index_from_storage, VectorStoreIndex, SimpleDirectoryReader # <--- AJOUTÉ
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo
from collections import Counter # <--- Importation ajoutée

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="API de Recherche Sémantique")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

INDEX_CACHE = {}


# --- Variables de configuration ---
ALL_INDEXES_DIR = "./all_indexes" # Dossier racine pour tous les index
DOCLING_URL = "http://10.95.33.115:30842/v1/convert/file" # Assurez-vous que Docling est accessible

# --- Modèles de données Pydantic ---
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

# --- Fonctions Helpers ---
def get_index_path(user_id: str, index_id: str) -> str:
    """Construit le chemin standardisé pour un index."""
    return os.path.join(ALL_INDEXES_DIR, user_id, index_id)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe par rapport à son hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashe un mot de passe."""
    return pwd_context.hash(password)

def run_indexing_logic(source_md_dir: str, index_dir: str):
    """Encapsule toute la logique de notre script ingest.py."""
    logger.info(f"Démarrage de l'indexation LlamaIndex pour le dossier : {source_md_dir}")
    init_settings() # S'assure que les settings sont chargés pour cette tâche
    
    pipeline = IngestionPipeline(
        transformations=[
            MarkdownNodeParser(include_metadata=True, include_prev_next_rel=True),
            FilterEmptyNodes(min_length=30, min_lines=3),
            RepairRelationships(),
        ]
    )
    
    documents = SimpleDirectoryReader(source_md_dir).load_data()
    parent_nodes = pipeline.run(documents=documents)
    
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


def remove_duplicate_headers(markdown_text: str) -> str:
    """
    Identifie les titres (#, ##, etc.) qui apparaissent plusieurs fois
    et ne conserve que leur première occurrence.
    """
    lines = markdown_text.splitlines()
    headers = [line.strip() for line in lines if line.strip().startswith("#")]
    header_counts = Counter(headers)
    duplicate_headers = {header for header, count in header_counts.items() if count > 1}

    cleaned_lines = []
    seen_duplicates = set()
    for line in lines:
        stripped_line = line.strip()
        if stripped_line in duplicate_headers:
            if stripped_line in seen_duplicates:
                continue
            else:
                seen_duplicates.add(stripped_line)
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)

def index_creation_task(
        user_id: str,
        index_id: str,
        files_info: List[dict],  # On passe des infos sur les fichiers, pas les objets
        metadata_json: str
):
    """
    Tâche de fond complète :
    1. Convertit les fichiers sources sauvegardés via Docling.
    2. Sauvegarde les .md résultants.
    3. Lance l'indexation LlamaIndex sur les .md.
    """
    index_path = get_index_path(user_id, index_id)
    source_files_dir = os.path.join(index_path, "source_files")
    md_files_dir = os.path.join(index_path, "md_files")
    index_dir = os.path.join(index_path, "index")
    os.makedirs(md_files_dir, exist_ok=True)

    try:
        metadata = json.loads(metadata_json)

        # --- Étape 1: Conversion de chaque fichier source ---
        for file_info in files_info:
            file_path = file_info["path"]
            filename = file_info["filename"]
            logger.info(f"Conversion du fichier '{filename}' via Docling...")

            with open(file_path, "rb") as f:
                response = requests.post(
                    DOCLING_URL,
                    files={'files': (filename, f)},
                    data={"table_mode": "accurate"}
                )
                response.raise_for_status()

            response.encoding = 'utf-8'

            # --- Étape 2: Sauvegarde du Markdown et des métadonnées ---
            md_content = response.json()["document"]["md_content"]

            logger.info(f"Nettoyage du contenu Markdown pour '{file_info['filename']}'...")
            cleaned_md = remove_duplicate_headers(md_content)  # On appelle la fonction de nettoyage

            source_url = metadata.get(file_info['filename'], "URL non fournie")

            md_filename = f"{os.path.splitext(file_info['filename'])[0]}.md"
            md_filepath = os.path.join(md_files_dir, md_filename)
            meta_filepath = os.path.join(md_files_dir, f"{md_filename}.meta")

            with open(md_filepath, "w", encoding="utf-8") as f:
                f.write(cleaned_md)  # On écrit le contenu NETTOYÉ
            with open(meta_filepath, "w", encoding="utf-8") as f:
                json.dump({"source_url": source_url}, f)

        # --- Étape 3: Lancer l'indexation LlamaIndex sur le dossier des .md ---
        run_indexing_logic(source_md_dir=md_files_dir, index_dir=index_dir)

    except Exception as e:
        logger.error(f"Erreur lors de la tâche d'indexation pour '{index_path}': {e}", exc_info=True)
        shutil.rmtree(index_path)

# --- Routes de l'API ---

# src/main.py

# ... (tous les imports et les helpers restent les mêmes) ...

@app.post("/index/{user_id}/{index_id}", status_code=status.HTTP_202_ACCEPTED, response_model=IndexResponse)
async def create_index(
        user_id: str,
        index_id: str,
        background_tasks: BackgroundTasks,
        files: List[UploadFile] = File(...),
        metadata_json: str = Form(...),
        password: Optional[str] = Form(None)
):
    """
    Crée ou met à jour un index de manière asynchrone.
    Si l'index existe, il est nettoyé avant d'être ré-indexé.
    """
    index_path = get_index_path(user_id, index_id)
    source_files_dir = os.path.join(index_path, "source_files")

    # --- NOUVELLE LOGIQUE "EXIST_OK" ---
    if os.path.exists(index_path):
        logger.info(f"L'index '{index_id}' existe déjà. Nettoyage des anciens fichiers générés...")
        # Supprimer les anciens résultats, mais PAS les sources
        for sub in ["md_files", "index", ".pw_hash"]:
            path_to_remove = os.path.join(index_path, sub)
            if os.path.exists(path_to_remove):
                if os.path.isdir(path_to_remove):
                    shutil.rmtree(path_to_remove)
                else:
                    os.remove(path_to_remove)
    else:
        # Si le dossier n'existe pas, on le crée
        os.makedirs(source_files_dir)

    # On s'assure que le dossier source existe (au cas où il aurait été supprimé manuellement)
    os.makedirs(source_files_dir, exist_ok=True)
    # --- FIN DE LA NOUVELLE LOGIQUE ---

    # La suite est identique : on sauvegarde les fichiers uploadés dans source_files
    files_info = []
    for file in files:
        file_path = os.path.join(source_files_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        files_info.append({"path": file_path, "filename": file.filename})

    if password:
        hashed_password = get_password_hash(password)
        with open(os.path.join(index_path, ".pw_hash"), "w") as f:
            f.write(hashed_password)

    background_tasks.add_task(index_creation_task, user_id, index_id, files_info, metadata_json)

    return {"status": "Accepted", "message": "Les fichiers ont été sauvegardés. L'indexation a démarré.",
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