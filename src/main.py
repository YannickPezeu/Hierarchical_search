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
from src.components import FilterEmptyNodes, RepairRelationships, AddBreadcrumbs, ContextMerger, normalize_filename
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException, status


# --- Imports de notre logique RAG ---
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo
from collections import Counter # <--- Importation ajoutée


from llama_index.core import StorageContext, load_index_from_storage, VectorStoreIndex, SimpleDirectoryReader
from llama_index.vector_stores.faiss import FaissVectorStore
import faiss

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





# ... (autres imports)

def run_indexing_logic(source_md_dir: str, index_dir: str):
    """Encapsule toute la logique de notre script ingest.py."""
    logger.info(f"Démarrage de l'indexation LlamaIndex pour le dossier : {source_md_dir}")
    init_settings() # S'assure que les settings sont chargés pour cette tâche

    # Le pipeline et la création des nodes ne changent pas
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

    # ▼▼▼ BLOC CORRIGÉ ▼▼▼

    # Mettez ici la dimension de votre modèle (voir point 2 ci-dessous)
    d = 4096 # Exemple à adapter

    # Initialiser un index FAISS
    faiss_index = faiss.IndexFlatL2(d)

    # Créer le VectorStore en utilisant l'index FAISS
    vector_store = FaissVectorStore(faiss_index=faiss_index)

    # Créer le StorageContext en fournissant notre vector_store.
    # LlamaIndex créera un docstore par défaut pour nous.
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # Ajouter tous les nodes (parents et enfants) au docstore
    storage_context.docstore.add_documents(all_nodes)

    # Construire l'index en utilisant les child_nodes pour le store de vecteurs
    index = VectorStoreIndex(nodes=child_nodes, storage_context=storage_context)

    # ▲▲▲ FIN DU BLOC CORRIGÉ ▲▲▲

    index.storage_context.persist(persist_dir=index_dir)
    logger.info(f"Indexation FAISS terminée et sauvegardée dans : {index_dir}")

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


# src/main.py

# ... (gardez tous vos imports et autres fonctions inchangés) ...

@app.post("/index/{user_id}/{index_id}", status_code=status.HTTP_202_ACCEPTED, response_model=IndexResponse)
async def create_index(
        user_id: str,
        index_id: str,
        background_tasks: BackgroundTasks,
        files: List[UploadFile] = File(...),
        metadata_json: Optional[str] = Form(None),
        password: Optional[str] = Form(None)
):
    """
    Crée ou met à jour un index de manière asynchrone.
    Si l'index existe, il est nettoyé avant d'être ré-indexé.
    """
    index_path = get_index_path(user_id, index_id)
    source_files_dir = os.path.join(index_path, "source_files")

    # --- LOGIQUE DE NETTOYAGE MODIFIÉE ---
    if os.path.exists(index_path):
        logger.info(f"L'index '{index_id}' existe déjà. Nettoyage des anciennes données d'index...")
        # On ne supprime que l'index et le hash du mot de passe, PAS les "md_files".
        for sub in ["index", ".pw_hash"]:
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
    # --- FIN DE LA LOGIQUE MODIFIÉE ---

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


def index_creation_task(
        user_id: str,
        index_id: str,
        files_info: List[dict],  # On passe des infos sur les fichiers, pas les objets
        metadata_json: str
):
    """
    Tâche de fond complète :
    1. Convertit les fichiers sources sauvegardés via Docling (si nécessaire).
    2. Répare les problèmes d'encodage potentiels de la réponse.
    3. Nettoie le contenu et le sauvegarde en .md.
    4. Lance l'indexation LlamaIndex sur les .md.
    """
    index_path = get_index_path(user_id, index_id)
    md_files_dir = os.path.join(index_path, "md_files")
    index_dir = os.path.join(index_path, "index")
    os.makedirs(md_files_dir, exist_ok=True)

    try:
        if metadata_json:
            metadata = json.loads(metadata_json)
        else:
            metadata = {}  # ✅ Safely handle the missing metadata
        # --- END OF MODIFICATION ---

        # --- Étape 1: Conversion de chaque fichier source ---
        for file_info in files_info:
            file_path = file_info["path"]
            original_filename = file_info["filename"]

            # --- NOUVELLE LOGIQUE POUR IGNORER LES FICHIERS EXISTANTS ---
            # Construire le chemin attendu pour le fichier .md

            normalized_basename, _ = os.path.splitext(normalize_filename(original_filename))
            md_filename = f"{normalized_basename}.md"
            md_filepath = os.path.join(md_files_dir, md_filename)


            # Vérifier si le fichier .md existe déjà
            if os.path.exists(md_filepath):
                logger.info(f"Le fichier Markdown '{md_filename}' existe déjà. La conversion Docling est ignorée.")
                continue  # Passer au fichier suivant
            # --- FIN DE LA NOUVELLE LOGIQUE ---

            logger.info(f"Conversion du fichier '{original_filename}' via Docling...")

            try:
                # La partie avec requests.post
                with open(file_path, "rb") as f:
                    response = requests.post(
                        DOCLING_URL,
                        files={'files': (original_filename, f)},
                        data={"table_mode": "accurate"},
                        # Ajouter un timeout côté client est une bonne pratique
                    )
                    # Cette ligne va lever une exception pour les erreurs 4xx/5xx
                    response.raise_for_status()

            except requests.exceptions.HTTPError as http_err:
                logger.error(f"Erreur HTTP de Docling pour le fichier '{original_filename}': {http_err}")
                logger.error(f"Réponse du serveur: {response.text}")
                # On passe au fichier suivant au lieu de faire planter toute la tâche
                continue
            except requests.exceptions.RequestException as req_err:
                logger.error(f"Erreur de connexion à Docling pour le fichier '{original_filename}': {req_err}")
                continue

            # --- Étape 2: Réparation de l'encodage et traitement du contenu ---
            raw_response_text = response.text
            try:
                repaired_json_string = raw_response_text.encode('latin-1').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError):
                repaired_json_string = raw_response_text

            response_data = json.loads(repaired_json_string)
            md_content = response_data.get("document", {}).get("md_content", "")

            # --- Étape 3: Nettoyage et sauvegarde ---
            logger.info(f"Nettoyage du contenu Markdown pour '{original_filename}'...")
            cleaned_md = remove_duplicate_headers(md_content)

            source_url = metadata.get(original_filename, "URL non fournie")

            # On utilise les variables md_filename et md_filepath déjà définies
            meta_filepath = os.path.join(md_files_dir, f"{md_filename}.meta")

            with open(md_filepath, "w", encoding="utf-8") as f:
                f.write(cleaned_md)
            with open(meta_filepath, "w", encoding="utf-8") as f:
                json.dump({"source_url": source_url}, f)

        # --- Étape 4: Lancer l'indexation LlamaIndex sur le dossier des .md ---
        run_indexing_logic(source_md_dir=md_files_dir, index_dir=index_dir)

    except Exception as e:
        logger.error(f"Erreur lors de la tâche d'indexation pour '{index_path}': {e}", exc_info=True)
        # --- GESTION D'ERREUR AMÉLIORÉE ---
        # En cas d'erreur, on ne supprime que l'index potentiellement corrompu, pas tout.
        if os.path.exists(index_dir):
            shutil.rmtree(index_dir)
        # --- FIN DE LA GESTION D'ERREUR ---

# --- Routes de l'API ---

# src/main.py

# ... (tous les imports et les helpers restent les mêmes) ...


# src/main.py

@app.post("/search/{user_id}/{index_id}", response_model=List[SearchResultNode])
async def search_in_index(user_id: str, index_id: str, request: SearchRequest):
    """
    Effectue une recherche dans un index existant, en utilisant un cache en mémoire.
    """
    index_path = get_index_path(user_id, index_id)
    index_dir = os.path.join(index_path, "index")

    if not os.path.exists(index_dir):
        raise HTTPException(status_code=404, detail="Index non trouvé.")

    # La vérification du mot de passe reste inchangée
    pw_file = os.path.join(index_path, ".pw_hash")
    if os.path.exists(pw_file):
        if not request.password:
            raise HTTPException(status_code=401, detail="Mot de passe requis pour cet index.")
        with open(pw_file, "r") as f:
            hashed_password = f.read()
        if not verify_password(request.password, hashed_password):
            raise HTTPException(status_code=403, detail="Mot de passe incorrect.")

    # --- LOGIQUE DE CACHING MISE À JOUR ---
    if index_dir not in INDEX_CACHE:
        # ▼▼▼ DÉBUT DU BLOC CORRIGÉ ▼▼▼
        logger.info(f"Index '{index_dir}' non trouvé dans le cache. Chargement spécifique à FAISS...")
        init_settings()

        # 1. Charger l'index FAISS binaire depuis le fichier
        # Le nom par défaut est 'default__vector_store.faiss'
        faiss_index_path = os.path.join(index_dir, "default__vector_store.json")
        if not os.path.exists(faiss_index_path):
            raise HTTPException(status_code=500, detail="Fichier d'index FAISS non trouvé. Veuillez ré-indexer.")

        faiss_index = faiss.read_index(faiss_index_path)

        # 2. Créer le FaissVectorStore à partir de l'index chargé
        vector_store = FaissVectorStore(faiss_index=faiss_index)

        # 3. Créer le StorageContext en spécifiant ce vector_store
        #    et en indiquant à LlamaIndex de charger le reste (docstore, etc.) depuis le dossier
        storage_context = StorageContext.from_defaults(
            vector_store=vector_store,
            persist_dir=index_dir
        )

        # 4. Charger l'index LlamaIndex principal à partir de ce contexte
        index = load_index_from_storage(storage_context)
        # ▲▲▲ FIN DU BLOC CORRIGÉ ▲▲▲

        # Le reste de la logique de création du retriever ne change pas
        base_retriever = index.as_retriever(similarity_top_k=5)
        merging_retriever = AutoMergingRetriever(
            vector_retriever=base_retriever,
            storage_context=storage_context,
        )
        INDEX_CACHE[index_dir] = (merging_retriever, storage_context)
        logger.info(f"Index FAISS '{index_dir}' chargé et mis en cache.")
    else:
        logger.info(f"Index '{index_dir}' trouvé dans le cache.")
        merging_retriever, storage_context = INDEX_CACHE[index_dir]

    # La logique de recherche et de post-processing reste la même
    retrieved_nodes = merging_retriever.retrieve(request.query)

    context_merger = ContextMerger(docstore=storage_context.docstore)
    add_breadcrumbs = AddBreadcrumbs()

    merged_nodes = context_merger.postprocess_nodes(retrieved_nodes, query_bundle=request.query)
    final_nodes = add_breadcrumbs.postprocess_nodes(merged_nodes, query_bundle=request.query)

    results = []
    for n in final_nodes:
        title = n.node.metadata.get("Header 2", n.node.metadata.get("Header 1", n.node.metadata.get("file_name",
                                                                                                    "Titre non trouvé")))
        results.append(SearchResultNode(
            content=n.node.get_content(),
            score=n.score,
            title=str(title),
            source_url=n.node.metadata.get("source_url", "URL non trouvée")
        ))

    return results