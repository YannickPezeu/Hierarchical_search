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
from src.components import FilterEmptyNodes, RepairRelationships, normalize_filename
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

def run_indexing_logic(source_md_dir: str, index_dir: str):
    logger.info(f"Starting LlamaIndex indexing for directory: {source_md_dir}")
    init_settings()
    pipeline = IngestionPipeline(
        transformations=[
            MarkdownNodeParser(include_metadata=True, include_prev_next_rel=True),
            FilterEmptyNodes(min_length=30, min_lines=3),
            RepairRelationships(),
        ]
    )
    documents = SimpleDirectoryReader(source_md_dir).load_data()
    parent_nodes = pipeline.run(documents=documents)
    child_splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
    all_nodes = []
    child_nodes = []
    for parent_node in parent_nodes:
        sub_nodes = child_splitter.get_nodes_from_documents([parent_node])
        header_metadata = {
            k: v for k, v in parent_node.metadata.items()
            if k.startswith("Header") or k == "header_path"
        }

        for sub_node in sub_nodes:
            sub_node.relationships[NodeRelationship.PARENT] = RelatedNodeInfo(node_id=parent_node.id_)
            sub_node.metadata.update(header_metadata)  # Copy header metadata to child

            child_nodes.append(sub_node)
        all_nodes.append(parent_node)
        all_nodes.extend(sub_nodes)

    d = 4096
    faiss_index = faiss.IndexFlatL2(d)
    vector_store = FaissVectorStore(faiss_index=faiss_index)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    storage_context.docstore.add_documents(all_nodes)
    index = VectorStoreIndex(nodes=child_nodes, storage_context=storage_context)
    index.storage_context.persist(persist_dir=index_dir)
    logger.info(f"FAISS indexing complete and saved to: {index_dir}")


# --- Background Task ---

def index_creation_task(index_id: str, files_info: List[dict], metadata_json: str):
    index_path = get_index_path(index_id)
    md_files_dir = os.path.join(index_path, "md_files")
    index_dir = os.path.join(index_path, "index")
    os.makedirs(md_files_dir, exist_ok=True)
    try:
        metadata = json.loads(metadata_json) if metadata_json else {}
        for file_info in files_info:
            file_path = file_info["path"]
            original_filename = file_info["filename"]
            normalized_basename, _ = os.path.splitext(normalize_filename(original_filename))
            md_filename = f"{normalized_basename}.md"
            md_filepath = os.path.join(md_files_dir, md_filename)
            if os.path.exists(md_filepath):
                logger.info(f"Markdown file '{md_filename}' already exists. Skipping Docling conversion.")
                continue
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

            raw_response_text = response.text
            try:
                repaired_json_string = raw_response_text.encode('latin-1').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError):
                repaired_json_string = raw_response_text

            response_data = json.loads(repaired_json_string)
            md_content = response_data.get("document", {}).get("md_content", "")

            md_content_final = reconstruct_markdown_hierarchy(md_content) if should_reconstruct_hierarchy(
                md_content) else md_content
            cleaned_md = remove_duplicate_headers(md_content_final)
            source_url = metadata.get(original_filename, "URL not provided")

            meta_filepath = os.path.join(md_files_dir, f"{md_filename}.meta")
            with open(md_filepath, "w", encoding="utf-8") as f:
                f.write(cleaned_md)
            with open(meta_filepath, "w", encoding="utf-8") as f:
                json.dump({"source_url": source_url}, f)

        run_indexing_logic(source_md_dir=md_files_dir, index_dir=index_dir)
    except Exception as e:
        logger.error(f"Error during indexing task for '{index_path}': {e}", exc_info=True)
        if os.path.exists(index_dir):
            shutil.rmtree(index_dir)