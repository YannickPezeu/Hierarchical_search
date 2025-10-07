# src/core/indexing.py
import os
import re
import json
import logging
import shutil
from typing import List
from collections import Counter
import requests
import faiss

# LlamaIndex Imports
from llama_index.core import (
    StorageContext, VectorStoreIndex, SimpleDirectoryReader,
    QueryBundle
)
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo
from llama_index.vector_stores.faiss import FaissVectorStore

# Local Project Imports
from src.settings import init_settings
from src.components import RepairRelationships, normalize_filename, MergeSmallNodes, \
    FilterTableOfContentsWithLLM
from src.core.config import DOCLING_URL
from src.core.utils import get_index_path

logger = logging.getLogger(__name__)


# --- Markdown Processing Helpers ---

def should_reconstruct_hierarchy(markdown_text: str) -> bool:
    header_levels = set()
    lines = markdown_text.splitlines()
    for line in lines:
        stripped_line = line.strip()
        if stripped_line.startswith("#"):
            if stripped_line.startswith("###"):
                header_levels.add(3)
            elif stripped_line.startswith("##"):
                header_levels.add(2)
            elif stripped_line.startswith("#"):
                header_levels.add(1)
    if 2 in header_levels and 1 not in header_levels and 3 not in header_levels:
        logger.info("Diagnostic: Flat hierarchy detected (only H2). Reconstruction necessary.")
        return True
    logger.info("Diagnostic: Title hierarchy seems correct. No reconstruction performed.")
    return False


def reconstruct_markdown_hierarchy(markdown_text: str) -> str:
    repaired_lines = []
    lines = markdown_text.splitlines()
    for line in lines:
        stripped_line = line.strip()
        if stripped_line.startswith("## "):
            title_text = stripped_line[3:]
            if re.match(r"^SECTION\s", title_text, re.IGNORECASE):
                repaired_lines.append(f"# {title_text}")
            elif re.match(r"^(CHAPITRE|TITRE)\s", title_text, re.IGNORECASE):
                repaired_lines.append(f"## {title_text}")
            elif re.match(r"^Art(?:icle)?\.?\s+\d+", title_text, re.IGNORECASE):
                repaired_lines.append(f"### {title_text}")
            else:
                repaired_lines.append(line)
        else:
            repaired_lines.append(line)
    return "\n".join(repaired_lines)


def remove_duplicate_headers(markdown_text: str) -> str:
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


# --- Core Indexing Logic ---

# Dans src/core/indexing.py
# Remplacer la fonction run_indexing_logic par ceci:

# Dans src/core/indexing.py
# Remplacer la fonction run_indexing_logic par ceci:

def run_indexing_logic(source_md_dir: str, index_dir: str):
    logger.info(f"Starting LlamaIndex indexing for directory: {source_md_dir}")
    init_settings()

    # Pipeline de transformation
    pipeline = IngestionPipeline(
        transformations=[
            MarkdownNodeParser(include_metadata=True, include_prev_next_rel=True),
            FilterTableOfContentsWithLLM(),
            # MergeSmallNodes crée maintenant une hiérarchie à 2 niveaux:
            # tiny (< 200) -> child (1000-2000) -> parent (2000-5000)
            # Les tiny nodes sont jetés après fusion
            MergeSmallNodes(
                tiny_size=200,
                child_min_size=1000,
                child_max_size=2000,
                parent_min_size=2000,
                parent_max_size=5000
            ),
            RepairRelationships(),
        ]
    )

    documents = SimpleDirectoryReader(source_md_dir).load_data()
    all_nodes = pipeline.run(documents=documents)

    # Séparer child nodes et parent nodes
    child_nodes = []
    parent_nodes = []

    for node in all_nodes:
        if NodeRelationship.PARENT in node.relationships:
            # Ce node a un parent, c'est donc un child
            child_nodes.append(node)
        else:
            # Ce node n'a pas de parent, c'est donc un parent
            parent_nodes.append(node)

    logger.info(f"📊 Hiérarchie créée:")
    logger.info(f"  • Child nodes (1000-2000 chars): {len(child_nodes)}")
    logger.info(f"  • Parent nodes (2000-5000 chars): {len(parent_nodes)}")

    # Créer des sub-chunks (512 tokens) UNIQUEMENT à partir des CHILD nodes pour l'embedding
    child_splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
    sub_chunks = []

    logger.info(f"📦 Création des sub-chunks pour l'indexation...")
    for child_node in child_nodes:
        chunks = child_splitter.get_nodes_from_documents([child_node])

        # Chaque sub-chunk pointe vers son child node parent
        for chunk in chunks:
            chunk.relationships[NodeRelationship.PARENT] = RelatedNodeInfo(node_id=child_node.id_)
            # Copier les metadata importantes
            chunk.metadata.update({
                k: v for k, v in child_node.metadata.items()
                if k.startswith("Header") or k in ["header_path", "file_name", "source_url"]
            })
            sub_chunks.append(chunk)

    logger.info(f"  • Sub-chunks créés: {len(sub_chunks)}")

    # Créer l'index vectoriel
    d = 4096
    faiss_index = faiss.IndexFlatL2(d)
    vector_store = FaissVectorStore(faiss_index=faiss_index)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # Ajouter TOUS les nodes au docstore (sub-chunks, children, parents)
    # Nécessaire pour remonter la hiérarchie lors du retrieval
    all_nodes_for_docstore = sub_chunks + child_nodes + parent_nodes
    storage_context.docstore.add_documents(all_nodes_for_docstore)

    logger.info(f"📦 Docstore:")
    logger.info(f"  • Sub-chunks (embedding): {len(sub_chunks)}")
    logger.info(f"  • Child nodes: {len(child_nodes)}")
    logger.info(f"  • Parent nodes: {len(parent_nodes)}")
    logger.info(f"  • TOTAL: {len(all_nodes_for_docstore)}")

    # Indexer UNIQUEMENT les sub-chunks pour l'embedding vectoriel
    index = VectorStoreIndex(nodes=sub_chunks, storage_context=storage_context)
    index.storage_context.persist(persist_dir=index_dir)

    logger.info(f"✅ Indexation complète:")
    logger.info(f"  • Vector index: {len(sub_chunks)} sub-chunks indexés")
    logger.info(f"  • Docstore: {len(all_nodes_for_docstore)} nodes stockés")
    logger.info(f"  • Hiérarchie: sub-chunk -> child -> parent")


def index_creation_task(index_id: str, files_info: List[dict], metadata_json: str):
    index_path = get_index_path(index_id)
    md_files_dir = os.path.join(index_path, "md_files")
    index_dir = os.path.join(index_path, "index")
    source_files_archive = os.path.join(index_path, "source_files_archive")

    os.makedirs(md_files_dir, exist_ok=True)
    os.makedirs(source_files_archive, exist_ok=True)

    try:
        metadata = json.loads(metadata_json) if metadata_json else {}
        seen_basenames = set()

        for file_info in files_info:
            file_path = file_info["path"]
            original_filename = file_info["filename"]
            normalized_basename, ext = os.path.splitext(normalize_filename(original_filename))

            # Vérifier les doublons
            if normalized_basename in seen_basenames:
                logger.error(f"Duplicate filename detected: {normalized_basename}")
                raise ValueError(
                    f"Cannot index multiple files with the same base name: {normalized_basename}"
                )
            seen_basenames.add(normalized_basename)

            # Archiver le fichier source
            archived_filename = f"{normalized_basename}{ext}"
            archive_destination = os.path.join(source_files_archive, archived_filename)
            if file_path != archive_destination:
                shutil.copy2(file_path, archive_destination)
            logger.info(f"File archived: {archived_filename} ({ext})")

            # Préparer le fichier Markdown
            md_filename = f"{normalized_basename}.md"
            md_filepath = os.path.join(md_files_dir, md_filename)

            if os.path.exists(md_filepath):
                logger.info(f"Markdown file '{md_filename}' already exists. Skipping Docling conversion.")
                continue

            # Conversion via Docling
            logger.info(f"Converting file '{original_filename}' via Docling...")
            try:
                with open(file_path, "rb") as f:
                    response = requests.post(
                        DOCLING_URL,
                        files={'files': (original_filename, f)},
                        data={"table_mode": "accurate"},
                    )
                    response.raise_for_status()
            except requests.exceptions.RequestException as req_err:
                logger.error(f"Docling connection error for '{original_filename}': {req_err}")
                continue

            # Traitement de la réponse
            raw_response_text = response.text
            try:
                repaired_json_string = raw_response_text.encode('latin-1').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError):
                repaired_json_string = raw_response_text

            response_data = json.loads(repaired_json_string)
            print('keys in response_data:', response_data.keys())
            print("Keys in document:", response_data["document"].keys())
            print("\nSample of document structure:")
            import pprint
            pprint.pprint(response_data["document"], depth=2)

            md_content = response_data.get("document", {}).get("md_content", "")

            # Nettoyage du Markdown
            md_content_final = reconstruct_markdown_hierarchy(md_content) if should_reconstruct_hierarchy(
                md_content) else md_content
            cleaned_md = remove_duplicate_headers(md_content_final)
            source_url = metadata.get(original_filename, "URL not provided")

            # Sauvegarder le Markdown et les métadonnées
            meta_filepath = os.path.join(md_files_dir, f"{md_filename}.meta")
            with open(md_filepath, "w", encoding="utf-8") as f:
                f.write(cleaned_md)
            with open(meta_filepath, "w", encoding="utf-8") as f:
                json.dump({
                    "source_url": source_url,
                    "source_filename": archived_filename
                }, f)

        # Lancer l'indexation
        run_indexing_logic(source_md_dir=md_files_dir, index_dir=index_dir)

    except Exception as e:
        logger.error(f"Error during indexing task for '{index_path}': {e}", exc_info=True)
        if os.path.exists(index_dir):
            shutil.rmtree(index_dir)