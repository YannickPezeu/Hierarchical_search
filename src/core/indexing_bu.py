# src/core/indexing.py - VERSION HIÉRARCHIQUE
import os
import re
import json
import logging
import shutil
from typing import List
from collections import Counter
from pathlib import Path
import requests
import faiss
import pymupdf
from rapidfuzz import fuzz
from bs4 import BeautifulSoup
from tqdm import tqdm

from llama_index.core import (
    StorageContext, VectorStoreIndex, SimpleDirectoryReader,
    QueryBundle
)
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo
from llama_index.vector_stores.faiss import FaissVectorStore

from src.settings import init_settings
from src.components import (
    RepairRelationships, normalize_filename, MergeSmallNodes,
    FilterTableOfContentsWithLLM
)
from src.core.config import DOCLING_URL
from src.core.utils import get_index_path
from src.core.indexing_html import _annotate_html_with_anchors, clean_html_before_docling
import time
from src.core.cache import search_cache



logger = logging.getLogger(__name__)


# ============================================================================
# HELPER FUNCTIONS POUR CHEMINS HIÉRARCHIQUES
# ============================================================================

def extract_relative_path(full_path: str, base_dir: str) -> str:
    """
    Extrait le chemin relatif depuis un dossier de base.

    Args:
        full_path: /path/to/source_files/campus/services/hash/file.pdf
        base_dir: /path/to/source_files

    Returns:
        campus/services/hash/file.pdf
    """
    return os.path.relpath(full_path, base_dir)


def get_parent_dir_path(relative_path: str) -> str:
    """
    Retourne le chemin du dossier parent depuis un chemin relatif.

    Args:
        relative_path: campus/services/hash/file.pdf

    Returns:
        campus/services/hash
    """
    return os.path.dirname(relative_path)


# ============================================================================
# MARKDOWN PROCESSING (inchangé)
# ============================================================================

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


# ============================================================================
# ANNOTATION (logique inchangée, mais chemins adaptés)
# ============================================================================

def annotate_documents_with_node_anchors(
        nodes: List,
        source_files_archive: str,
        md_files_dir: str
) -> List:
    """
    Modifie les documents sources (PDF/HTML) pour insérer des ancres/destinations
    pointant vers chaque child node.

    ⚠️ VERSION HIÉRARCHIQUE : Gère les chemins relatifs dans l'arborescence
    """
    logger.info(f"\n{'=' * 80}")
    logger.info(f"ANNOTATION DES DOCUMENTS AVEC ANCRES DE NODES (HIÉRARCHIQUE)")
    logger.info(f"{'=' * 80}")

    nodes_by_document = {}
    for node in nodes:
        file_name = node.metadata.get("file_name", "")
        if not file_name:
            continue
        if file_name not in nodes_by_document:
            nodes_by_document[file_name] = []
        nodes_by_document[file_name].append(node)

    total_annotated = 0
    total_skipped_parents = 0
    total_failed = 0

    for md_filename, doc_nodes in nodes_by_document.items():
        # ✅ NOUVEAU : Chercher le .meta dans l'arborescence
        meta_file = find_meta_file_in_tree(md_files_dir, md_filename)

        if not meta_file:
            logger.warning(f"⚠️ Métadonnées introuvables pour {md_filename}")
            total_failed += len(doc_nodes)
            continue

        with open(meta_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        source_filename = metadata.get("source_filename", "")
        source_relative_path = metadata.get("source_relative_path", "")

        if not source_filename:
            logger.warning(f"⚠️ Nom de fichier source manquant pour {md_filename}")
            total_failed += len(doc_nodes)
            continue

        # ✅ NOUVEAU : Construire le chemin complet avec la hiérarchie
        if source_relative_path:
            source_path = os.path.join(source_files_archive, source_relative_path)
        else:
            # Fallback pour anciens fichiers sans source_relative_path
            source_path = os.path.join(source_files_archive, source_filename)

        if not os.path.exists(source_path):
            logger.warning(f"⚠️ Fichier source introuvable : {source_path}")
            total_failed += len(doc_nodes)
            continue

        # Séparer child nodes (à annoter) et parent nodes (à skipper)
        child_nodes = [n for n in doc_nodes if NodeRelationship.PARENT in n.relationships]
        parent_nodes = [n for n in doc_nodes if NodeRelationship.PARENT not in n.relationships]

        logger.info(f"\n📄 Traitement de {source_relative_path or source_filename}")
        logger.info(f"   • {len(child_nodes)} child nodes à annoter")
        logger.info(f"   • {len(parent_nodes)} parent nodes (recevront un ID de fallback)")

        # Parent nodes : ID de fallback
        for parent in parent_nodes:
            parent.metadata['node_anchor_id'] = f"node_{parent.id_}"
        total_skipped_parents += len(parent_nodes)

        nodes_to_annotate = child_nodes

        _, ext = os.path.splitext(source_filename)
        ext_lower = ext.lower()

        if nodes_to_annotate:
            if ext_lower == '.pdf':
                annotated = _annotate_pdf_with_destinations(nodes_to_annotate, source_path)
                total_annotated += annotated
                total_failed += (len(nodes_to_annotate) - annotated)

            elif ext_lower in ['.html', '.htm']:
                annotated = _annotate_html_with_anchors(nodes_to_annotate, source_path)
                total_annotated += annotated
                total_failed += (len(nodes_to_annotate) - annotated)

            else:
                logger.info(f"   Type de fichier non supporté : {ext_lower}, assignation d'IDs de fallback.")
                for node in nodes_to_annotate:
                    node.metadata['node_anchor_id'] = f"node_{node.id_}"
                total_annotated += len(nodes_to_annotate)

    logger.info(f"\n{'=' * 80}")
    logger.info(f"RÉSULTAT DE L'ANNOTATION")
    logger.info(f"{'=' * 80}")
    logger.info(f"  ✅ Child nodes annotés : {total_annotated}")
    logger.info(f"  ⭐ Parent nodes (ignorés) : {total_skipped_parents}")
    logger.info(f"  ❌ Échecs : {total_failed}")
    logger.info(f"{'=' * 80}\n")

    return nodes


def find_meta_file_in_tree(base_dir: str, md_filename: str) -> str:
    """
    Cherche un fichier .meta dans toute l'arborescence.

    Args:
        base_dir: Racine de l'arborescence (md_files/)
        md_filename: Nom du fichier .md (ex: "guide.md")

    Returns:
        Chemin complet vers le .meta ou None
    """
    meta_filename = f"{md_filename}.meta"

    for root, dirs, files in os.walk(base_dir):
        if meta_filename in files:
            return os.path.join(root, meta_filename)

    return None


def clean_markdown_whitespace(markdown_text: str) -> str:
    """
    Nettoie les espaces inutiles et les images base64 dans le markdown pour réduire les tokens.

    - Supprime complètement les images encodées en base64
    - Réduit les séquences d'espaces multiples dans les tableaux
    - Raccourcit les lignes de séparateurs (---, ___, etc.)
    - Conserve la structure du markdown pour qu'il s'affiche correctement
    """
    original_length = len(markdown_text)

    # ✨ ÉTAPE 1 : Supprimer complètement les images base64
    # Pattern pour détecter et supprimer ![texte](data:image/...)
    markdown_text = re.sub(
        r'!\[([^\]]*)\]\(data:image/[^;]+;base64,[A-Za-z0-9+/=]+\)',
        '',  # Suppression complète
        markdown_text
    )

    # Pattern alternatif pour images sans texte alt
    markdown_text = re.sub(
        r'!\[\]\(data:image/[^;]+;base64,[A-Za-z0-9+/=]+\)',
        '',  # Suppression complète
        markdown_text
    )

    # ÉTAPE 2 : Nettoyer les lignes
    lines = markdown_text.splitlines()
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        # Détecter les lignes de séparateurs de tableaux markdown
        if '|' in line and re.match(r'^[\s\|\-_=:]+$', stripped):
            num_pipes = stripped.count('|')
            if num_pipes >= 2:
                separator = '| ' + ' | '.join(['---'] * (num_pipes - 1)) + ' |'
                cleaned_lines.append(separator)
            else:
                cleaned_lines.append(stripped)

        # Lignes de tableaux normales (avec du contenu)
        elif '|' in line:
            cleaned_line = re.sub(r'\s*\|\s*', ' | ', line)
            cleaned_line = re.sub(r'\s{2,}', ' ', cleaned_line)
            cleaned_lines.append(cleaned_line.strip())

        # Autres lignes de séparateurs (headers, etc.)
        elif re.match(r'^[\s\-_=.]+$', stripped):
            if '-' in line:
                cleaned_lines.append('---')
            elif '_' in line:
                cleaned_lines.append('___')
            elif '=' in line:
                cleaned_lines.append('===')
            elif '.' in line:
                cleaned_lines.append('...')
            else:
                cleaned_lines.append(stripped)

        else:
            # Pour les lignes normales, réduire simplement les espaces multiples
            cleaned_line = re.sub(r'\s{3,}', '  ', line)
            cleaned_lines.append(cleaned_line)

    # Réduire les lignes vides consécutives à maximum 2
    result = '\n'.join(cleaned_lines)
    result = re.sub(r'\n{4,}', '\n\n\n', result)

    cleaned_length = len(result)
    reduction_percent = ((original_length - cleaned_length) / original_length * 100) if original_length > 0 else 0

    logger.info(
        f"  📊 Markdown cleaned: {original_length:,} → {cleaned_length:,} chars ({reduction_percent:.1f}% reduction)")

    return result

# Modified section of index_creation_task function
# Replace the duplicate checking section (around lines 395-410) with:

def make_windows_long_path(path):
    """
    Convertit un chemin en chemin long Windows (préfixé \\?\) si nécessaire.
    """
    if os.name == 'nt' and not path.startswith('\\\\?\\'):
        # Convertir en chemin absolu d'abord
        abs_path = os.path.abspath(path)
        return '\\\\?\\' + abs_path
    return path


def index_creation_task(index_id: str, files_info: List[dict], metadata_json: str):
    """
    Tâche d'indexation complète avec support hiérarchique.
    """
    index_path = get_index_path(index_id)
    md_files_dir = os.path.join(index_path, "md_files")
    index_dir = os.path.join(index_path, "index")
    source_files_archive = os.path.join(index_path, "source_files_archive")
    source_files_temp = os.path.join(index_path, "source_files")

    # Créer un fichier de statut "en cours"
    status_file = os.path.join(index_path, ".indexing_status")
    start_time = time.time()
    with open(status_file, "w") as f:
        json.dump({"status": "in_progress", "started_at": start_time}, f)

    # ✨ NOUVEAU : Nettoyer le cache pour cet index lors de la réindexation
    logger.info(f"🗑️  Clearing cache for index: {index_id}")
    search_cache.clear_index_cache(index_path)

    os.makedirs(md_files_dir, exist_ok=True)
    os.makedirs(source_files_archive, exist_ok=True)

    try:
        # ✅ NOUVEAU : Construire un dictionnaire des vraies URLs depuis metadata_json
        true_urls_map = {}  # {filename: true_url}

        if metadata_json:
            try:
                metadata = json.loads(metadata_json)
                true_urls_map = metadata  # Format: {"file.pdf": "https://real-url.com/file.pdf"}
                logger.info(f"📋 Loaded {len(true_urls_map)} URL mappings from metadata")
            except json.JSONDecodeError:
                logger.warning("⚠️ Failed to parse metadata_json, will use fallback URLs")
                metadata = {}
        else:
            metadata = {}

        seen_basenames = set()
        skipped_duplicates = []  # Track skipped duplicate files
        skipped_validation = []

        files_info = [
            f for f in files_info
            if f["filename"].lower() not in ["metadata.json"]
        ]

        if not files_info:
            raise ValueError("No valid files to index after filtering crawler artifacts (metadata.json)")

        logger.info(f"📄 Files to index after filtering: {len(files_info)}")

        # ========================================
        # PHASE 1 : CONVERSION DES FICHIERS
        # ========================================
        for file_info in files_info:
            file_path = file_info["path"]
            original_filename = file_info["filename"]

            # ✅ Extraire le chemin relatif
            relative_path = file_info.get("relative_path")

            if not relative_path:
                relative_path = extract_relative_path(file_path, source_files_temp)

            # Normaliser le nom de fichier
            normalized_basename, ext = os.path.splitext(normalize_filename(original_filename))

            # ✅ BLOQUER LES .doc
            if ext.lower() == '.doc':
                logger.warning(f"⚠️ Skipping unsupported format: {original_filename} (.doc)")
                skipped_validation.append({
                    "filename": original_filename,
                    "reason": "unsupported_format",
                    "type": ".doc"
                })
                continue

            # ✅ VALIDER LES PDFs
            if ext.lower() == '.pdf':
                try:
                    # Vérifier les magic bytes (signature PDF)
                    with open(file_path, 'rb') as f:
                        header = f.read(5)

                    if not header.startswith(b'%PDF-'):
                        logger.error(f"❌ Invalid PDF signature (not a real PDF): {original_filename}")
                        logger.error(f"   Header bytes: {header}")
                        logger.error(f"   This looks like: {header.decode('utf-8', errors='ignore')}")
                        logger.error(f"   Deleting fake PDF: {file_path}")
                        os.remove(file_path)
                        skipped_validation.append({
                            "filename": original_filename,
                            "reason": "invalid_pdf_signature",
                            "header": header.decode('utf-8', errors='ignore')[:50]
                        })
                        continue

                    # Vérifier avec PyMuPDF
                    start = time.time()
                    test_doc = pymupdf.open(file_path)

                    num_pages = len(test_doc)

                    if num_pages == 0:
                        test_doc.close()
                        logger.error(f"❌ PDF has no pages: {original_filename}")
                        logger.error(f"   Deleting corrupted file: {file_path}")
                        os.remove(file_path)
                        skipped_validation.append({
                            "filename": original_filename,
                            "reason": "pdf_no_pages"
                        })
                        continue

                    # Vérifier qu'on peut lire au moins une page
                    try:
                        first_page_text = test_doc[0].get_text()
                        test_doc.close()
                    except Exception as read_error:
                        test_doc.close()
                        logger.error(f"❌ Cannot read PDF pages: {original_filename}")
                        logger.error(f"   Error: {read_error}")
                        logger.error(f"   Deleting file: {file_path}")
                        os.remove(file_path)
                        skipped_validation.append({
                            "filename": original_filename,
                            "reason": "pdf_unreadable",
                            "error": str(read_error)
                        })
                        continue

                    elapsed = time.time() - start
                    logger.info(f"✅ PDF OK: {num_pages} pages, validation took {elapsed * 1000:.0f}ms")

                except Exception as e:
                    logger.error(f"❌ Error validating PDF: {original_filename}")
                    logger.error(f"   Error: {e}")
                    logger.error(f"   Deleting file: {file_path}")

                    try:
                        os.remove(file_path)
                        logger.info(f"   ✅ File deleted successfully")
                    except Exception as del_error:
                        logger.error(f"   ⚠️ Failed to delete file: {del_error}")

                    skipped_validation.append({
                        "filename": original_filename,
                        "reason": "pdf_validation_error",
                        "error": str(e)
                    })
                    continue

            relative_dir = os.path.dirname(relative_path)
            md_dir_for_file = os.path.join(md_files_dir, relative_dir)

            md_filename = f"{normalized_basename}.md"
            md_filepath = os.path.join(md_dir_for_file, md_filename)
            # --- FIN : Calcul des chemins cibles ---

            # ✅ OPTIMISATION : Check AVANT toute opération I/O
            if os.path.exists(md_filepath):
                logger.info(f"Markdown exists, skipping: {os.path.join(relative_dir, md_filename)}")
                continue

            # Vérifier doublons - MODIFIED SECTION
            if normalized_basename in seen_basenames:
                if normalized_basename == 'metadata':
                    # Allow metadata duplicates
                    pass
                else:
                    # Log warning and skip duplicate file instead of raising error
                    logger.warning(f"⚠️ Duplicate filename detected: {normalized_basename}")
                    logger.warning(f"   Skipping file: {original_filename} at {relative_path}")
                    skipped_duplicates.append({
                        "filename": original_filename,
                        "normalized": normalized_basename,
                        "path": relative_path
                    })
                    continue  # Skip to next file

            seen_basenames.add(normalized_basename)

            # ✅ Reproduire la hiérarchie dans source_files_archive
            archive_dir_for_file = os.path.join(source_files_archive, relative_dir)
            os.makedirs(archive_dir_for_file, exist_ok=True)

            archived_filename = f"{normalized_basename}{ext}"
            archive_destination = make_windows_long_path(
                os.path.join(archive_dir_for_file, archived_filename)
            )
            archived_relative_path = os.path.join(relative_dir,
                                                  archived_filename) if relative_dir else archived_filename

            # Copier vers source_files_archive
            if file_path != archive_destination:
                shutil.copy2(file_path, archive_destination)
                logger.info(f"File archived: {archived_relative_path}")

            # ✅ Reproduire la hiérarchie dans md_files
            os.makedirs(md_dir_for_file, exist_ok=True)

            md_filename = f"{normalized_basename}.md"
            md_filepath = os.path.join(md_dir_for_file, md_filename)
            meta_filepath = md_filepath + ".meta"

            # ✅ CORRECTION : Extraire la vraie URL depuis true_urls_map
            # Pour les fichiers HTML, chercher l'entrée qui se termine par /page_xxx.html
            # Pour les autres fichiers, chercher par nom de fichier exact

            true_source_url = None

            if ext.lower() in ['.html', '.htm']:
                # Pour HTML : chercher dans metadata.json l'URL du dossier parent
                # Le scraper sauvegarde metadata.json avec "url" de la page
                parent_metadata_path = os.path.join(os.path.dirname(file_path), 'metadata.json')

                if os.path.exists(parent_metadata_path):
                    try:
                        with open(parent_metadata_path, 'r', encoding='utf-8') as f:
                            scraper_metadata = json.load(f)
                            true_source_url = scraper_metadata.get('url')
                            logger.info(f"  ✔ Found true URL from scraper metadata.json: {true_source_url}")
                    except Exception as e:
                        logger.warning(f"  ⚠️ Failed to read scraper metadata.json: {e}")
            else:
                # Pour les autres fichiers (PDF, DOCX, etc.) : chercher dans true_urls_map
                # Le scraper sauvegarde dans downloadedDocuments avec originalUrl
                parent_metadata_path = os.path.join(os.path.dirname(file_path), 'metadata.json')

                if os.path.exists(parent_metadata_path):
                    try:
                        with open(parent_metadata_path, 'r', encoding='utf-8') as f:
                            scraper_metadata = json.load(f)
                            downloaded_docs = scraper_metadata.get('downloadedDocuments', [])

                            # Chercher le document qui correspond à notre fichier
                            for doc in downloaded_docs:
                                if doc.get('fileName') == original_filename:
                                    true_source_url = doc.get('originalUrl')
                                    logger.info(f"  ✔ Found true URL from downloadedDocuments: {true_source_url}")
                                    break
                    except Exception as e:
                        logger.warning(f"  ⚠️ Failed to read scraper metadata.json: {e}")

            # Fallback si aucune URL trouvée
            if not true_source_url:
                true_source_url = true_urls_map.get(original_filename, f"URL not found for {original_filename}")
                logger.warning(f"  ⚠️ Using fallback URL: {true_source_url}")

            # Créer le fichier .meta avec la VRAIE URL
            if not os.path.exists(meta_filepath):
                with open(meta_filepath, "w", encoding="utf-8") as f:
                    json.dump({
                        "source_url": true_source_url,  # ← VRAIE URL
                        "source_filename": archived_filename,
                        "source_relative_path": archived_relative_path
                    }, f, indent=2)
                logger.info(f"Metadata file created: {os.path.join(relative_dir, md_filename + '.meta')}")
                logger.info(f"  URL: {true_source_url}")



            # Nettoyage HTML si nécessaire
            if ext.lower() in ['.html', '.htm']:
                logger.info(f"🌐 HTML detected: {original_filename}")
                try:
                    cleaned_html_path = clean_html_before_docling(archive_destination)
                    file_to_convert = cleaned_html_path
                    cleanup_temp = True
                except Exception as e:
                    logger.warning(f"⚠️ HTML cleaning failed: {e}")
                    file_to_convert = archive_destination
                    cleanup_temp = False
            else:
                file_to_convert = archive_destination
                cleanup_temp = False

            # Conversion via Docling
            logger.info(f"Converting file via Docling: {original_filename}")
            try:
                with open(file_to_convert, "rb") as f:
                    response = requests.post(
                        DOCLING_URL,
                        files={'files': (original_filename, f)},
                        data={"table_mode": "accurate"},
                    )
                    response.raise_for_status()
            except requests.exceptions.RequestException as req_err:
                logger.error(f"Docling error for '{original_filename}': {req_err}")
                if cleanup_temp and os.path.exists(file_to_convert):
                    os.remove(file_to_convert)
                continue
            finally:
                if cleanup_temp and os.path.exists(file_to_convert):
                    os.remove(file_to_convert)

            # Traitement de la réponse Docling
            raw_response_text = response.text
            try:
                repaired_json_string = raw_response_text.encode('latin-1').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError):
                repaired_json_string = raw_response_text

            response_data = json.loads(repaired_json_string)
            md_content = response_data.get("document", {}).get("md_content", "")

            # Nettoyage du Markdown
            md_content_final = reconstruct_markdown_hierarchy(md_content) if should_reconstruct_hierarchy(
                md_content) else md_content
            cleaned_md = remove_duplicate_headers(md_content_final)

            # Nettoyer les espaces inutiles pour réduire les tokens
            cleaned_md = clean_markdown_whitespace(cleaned_md)

            # Sauvegarder le Markdown
            with open(md_filepath, "w", encoding="utf-8") as f:
                f.write(cleaned_md)
            logger.info(f"✔ Markdown saved: {os.path.join(relative_dir, md_filename)}")

        # Log summary of skipped duplicates
        if skipped_duplicates:
            logger.warning(f"\n{'=' * 80}")
            logger.warning(f"⚠️ DUPLICATE FILES SKIPPED: {len(skipped_duplicates)}")
            logger.warning(f"{'=' * 80}")
            for dup in skipped_duplicates:
                logger.warning(f"  • {dup['filename']} → {dup['normalized']} at {dup['path']}")
            logger.warning(f"{'=' * 80}\n")

        # Log summary of skipped files due to validation
        if skipped_validation:
            logger.warning(f"\n{'=' * 80}")
            logger.warning(f"⚠️ FILES REJECTED BY VALIDATION: {len(skipped_validation)}")
            logger.warning(f"{'=' * 80}")
            for skip in skipped_validation:
                logger.warning(f"  • {skip['filename']} - Reason: {skip['reason']}")
            logger.warning(f"{'=' * 80}\n")

        # ========================================
        # PHASE 2 : INDEXATION LLAMAINDEX (inchangée)
        # ========================================
        logger.info(f"Starting LlamaIndex indexing for directory: {md_files_dir}")
        run_indexing_logic(source_md_dir=md_files_dir, index_dir=index_dir)

        # Marquer comme terminé avec succès
        end_time = time.time()
        actual_files_processed = len(files_info) - len(skipped_duplicates) - len(skipped_validation)

        with open(status_file, "w") as f:
            json.dump({
                "status": "completed",
                "started_at": start_time,
                "completed_at": end_time,
                "duration_seconds": end_time - start_time,
                "num_documents": actual_files_processed,
                "skipped_duplicates": len(skipped_duplicates),
                "skipped_files": [d["filename"] for d in skipped_duplicates]
            }, f)

        logger.info(f"✅ Indexation terminée avec succès pour {index_id} en {end_time - start_time:.1f}s")
        logger.info(f"   • Files processed: {actual_files_processed}")
        logger.info(f"   • Duplicates skipped: {len(skipped_duplicates)}")

    except Exception as e:
        end_time = time.time()
        with open(status_file, "w") as f:
            json.dump({
                "status": "failed",
                "error": str(e),
                "error_type": type(e).__name__,
                "started_at": start_time,
                "failed_at": end_time,
                "duration_seconds": end_time - start_time
            }, f)

        logger.error(f"❌ Error during indexing task for '{index_path}': {e}", exc_info=True)
        if os.path.exists(index_dir):
            shutil.rmtree(index_dir)
        raise


def load_metadata_from_meta_file_direct(meta_filepath: str) -> dict:
    """
    Charge les métadonnées depuis un fichier .meta (version avec chemin direct).
    """
    if not os.path.exists(meta_filepath):
        return {}

    try:
        with open(meta_filepath, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        return metadata
    except Exception as e:
        logger.warning(f"Failed to load .meta file {meta_filepath}: {e}")
        return {}


def load_metadata_from_meta_file(md_filepath: str) -> dict:
    """
    Charge les métadonnées depuis le fichier .meta correspondant au markdown.
    (Wrapper pour compatibilité)
    """
    meta_filepath = md_filepath + ".meta"
    return load_metadata_from_meta_file_direct(meta_filepath)


def _normalize_text_for_comparison(text: str) -> str:
    """
    Normalisation agressive pour comparaison fuzzy.
    Supprime toute la structure markdown/tableaux pour comparer le contenu pur.
    """
    # 1. Retirer les marqueurs markdown
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)  # Headers ##
    text = re.sub(r'\|', ' ', text)  # Pipes de tableaux
    text = re.sub(r'-{3,}', ' ', text)  # Séparateurs (---)
    text = re.sub(r'\.{4,}', ' ', text)  # Points multiples
    text = re.sub(r'={3,}', ' ', text)  # Séparateurs (===)

    # 2. Minuscules
    text = text.lower()

    # 3. Remplacer tous les non-alphanumériques par espaces
    text = re.sub(r'[^\w\sàâäéèêëïîôùûüÿçæœ]', ' ', text)

    # 4. Réduire tous les espaces multiples
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def _find_coords_on_page(doc, page_number: int, matched_text_from_pdf: str):
    """
    Cherche les coordonnées d'un texte dans une page PDF avec stratégie de fallback progressive.

    Args:
        doc: Document PyMuPDF ouvert
        page_number: Numéro de page (0-indexed)
        matched_text_from_pdf: Texte extrait du PDF à chercher

    Returns:
        Tuple (instances, strategy_used) ou (None, None)
    """
    try:
        page = doc[page_number]
        words = matched_text_from_pdf.split()

        if len(words) < 5:
            logger.debug(f"         -> Too few words ({len(words)}) for search")
            return None, None

        # Stratégie 1 : Premiers 15 mots
        search_phrase = " ".join(words[:15])
        logger.debug(f"         -> Strategy 1 (first 15 words): '{search_phrase[:100]}...'")
        instances = page.search_for(search_phrase, quads=False)
        if instances:
            return instances, "first_15_words"

        # Stratégie 2 : Fenêtre glissante de 15 mots
        max_iterations = min(100, len(words) - 15)

        for i in range(1, max_iterations):
            search_phrase = " ".join(words[i:i + 15])
            instances = page.search_for(search_phrase, quads=False)
            if instances:
                logger.debug(f"         -> Found with sliding window at offset {i}")
                return instances, f"sliding_window_offset_{i}"

        logger.debug(f"         -> Sliding window tried {max_iterations} positions, all failed")

        # Stratégie 3 : Si texte très court, essayer tout
        if len(words) < 30:
            logger.debug(f"         -> Strategy 3 (full text for short node): '{matched_text_from_pdf[:100]}...'")
            instances = page.search_for(matched_text_from_pdf, quads=False)
            if instances:
                return instances, "full_text"

        return None, None

    except Exception as e:
        logger.debug(f"         -> Search error: {e}")
        return None, None


def _is_table_node(text: str) -> bool:
    """
    Détecte si un node contient un tableau markdown.
    """
    # Indicateurs de tableaux
    has_pipes = '|' in text
    has_dashes = '-----' in text or '----' in text
    has_dots = '......' in text or '.....' in text
    has_underscores = '_____' in text or '____' in text

    return has_pipes or has_dashes or has_dots or has_underscores


def _annotate_pdf_with_destinations(nodes: List, pdf_path: str) -> int:
    """
    Version avec normalisation PUIS découpe.
    """
    try:
        doc = pymupdf.open(pdf_path)

        # Extraction (inchangé)
        page_char_offsets = {}
        pages_raw_text = {}
        pages_normalized_text = {}
        full_text = ""

        for page_num in range(len(doc)):
            page_text = doc[page_num].get_text("text")
            pages_raw_text[page_num] = page_text
            pages_normalized_text[page_num] = _normalize_text_for_comparison(page_text)
            page_char_offsets[page_num] = len(full_text)
            full_text += page_text + "\n"

        clean_full_text = re.sub(r'\s+', ' ', full_text).strip()
        normalized_full_text = _normalize_text_for_comparison(full_text)

        logger.info(f"   📖 PDF loaded: {len(doc)} pages, {len(clean_full_text):,} chars")

        annotated_count = 0
        toc = doc.get_toc()
        last_found_page = 0

        for idx, node in enumerate(nodes):
            logger.info(f"\n   🔄 Node {idx + 1}/{len(nodes)} (ID: {node.id_[:8]}...)")

            node_full_text = node.text

            # ✅ CHANGEMENT : Normaliser PUIS couper
            normalized_full_node = _normalize_text_for_comparison(node_full_text)

            if len(normalized_full_node) < 50:
                node.metadata['node_anchor_id'] = f"node_{node.id_}"
                continue

            # Couper APRÈS normalisation
            normalized_snippet = normalized_full_node[:300]

            # Pour les logs : garder aussi le snippet original correspondant
            # (approximation : prendre plus de caractères bruts pour avoir ~300 normalisés)
            search_snippet_for_logs = node_full_text[:600]  # Plus large pour les logs

            # Détection de tableau
            is_table = _is_table_node(node_full_text)
            confidence_threshold = 50 if is_table else 70

            if is_table:
                logger.info(f"      📊 Table detected - using lower threshold ({confidence_threshold}%)")

            logger.info(f"      📄 Starting search from last found page: {last_found_page + 1}")

            # Pages prioritaires
            pages_to_check = []
            pages_to_check.append(last_found_page)

            for offset in range(1, 5):
                if last_found_page - offset > 0:
                    pages_to_check.append(last_found_page - offset)

            logger.info(f"      🔍 Searching in priority pages: {[p + 1 for p in pages_to_check]}")

            best_page = last_found_page
            best_page_score = 0

            # Chercher dans les pages prioritaires
            for page_num in pages_to_check:
                normalized_page_text = pages_normalized_text[page_num]
                score = fuzz.partial_ratio(normalized_snippet, normalized_page_text)

                if score > best_page_score:
                    best_page_score = score
                    best_page = page_num
                    logger.debug(f"         -> Page {page_num + 1}: {score:.1f}% (new best)")

                    if score > 95:
                        break

            # Si le score est insuffisant, élargir À TOUT LE DOCUMENT
            if best_page_score < 90:
                logger.warning(
                    f"      ⚠️  Low score in priority pages ({best_page_score:.1f}%), searching ALL pages...")

                for page_num in range(len(doc)):  # ← TOUT le document, pas juste après
                    if page_num in pages_to_check:
                        continue  # Déjà vérifié

                    normalized_page_text = pages_normalized_text[page_num]
                    score = fuzz.partial_ratio(normalized_snippet, normalized_page_text)

                    if score > best_page_score:
                        best_page_score = score
                        best_page = page_num
                        logger.debug(f"         -> Page {page_num + 1}: {score:.1f}% (new best)")

            logger.info(f"      ✓ Best match: page {best_page + 1} (score: {best_page_score:.1f}%)")

            # Threshold adaptatif
            if best_page_score < confidence_threshold:
                logger.warning(
                    f"      ⚠️  Low confidence ({best_page_score:.1f}% < {confidence_threshold}%) - creating page-level anchor")
                logger.warning("=" * 80)
                logger.warning("      >>> DIAGNOSTIC: LOW CONFIDENCE NODE <<<")
                logger.warning("-" * 80)
                logger.warning(f"      [Is table]: {is_table}")
                logger.warning(f"      [Threshold used]: {confidence_threshold}%")
                logger.warning("-" * 80)
                logger.warning(f"      [Node content ORIGINAL] (length: {len(node_full_text)}):")
                logger.warning("-" * 80)
                logger.warning(node_full_text[:500])
                logger.warning("-" * 80)
                logger.warning(f"      [Search snippet ORIGINAL] (length: {len(search_snippet_for_logs)}):")
                logger.warning("-" * 80)
                logger.warning(search_snippet_for_logs)
                logger.warning("-" * 80)
                logger.warning(f"      [Search snippet NORMALIZED] (length: {len(normalized_snippet)}):")
                logger.warning("-" * 80)
                logger.warning(normalized_snippet)
                logger.warning("-" * 80)
                logger.warning(f"      [Best match was on page {best_page + 1}]")
                logger.warning(f"      [Page {best_page + 1} text ORIGINAL - first 500 chars]:")
                logger.warning("-" * 80)
                logger.warning(pages_raw_text[best_page][:500])
                logger.warning("-" * 80)
                logger.warning(f"      [Page {best_page + 1} text NORMALIZED - first 300 chars]:")
                logger.warning("-" * 80)
                logger.warning(pages_normalized_text[best_page])
                logger.warning("=" * 80)

                dest_name = f"node_{node.id_}"
                toc.append([1, dest_name, best_page + 1])
                node.metadata.update({
                    'node_anchor_id': dest_name,
                    'page_number': best_page + 1,
                    'page_confidence': best_page_score,
                    'anchor_type': 'page_level_low_confidence',
                    'is_table': is_table
                })
                annotated_count += 1
                last_found_page = best_page
                continue

            target_page_num = best_page
            page_text_content = pages_raw_text[target_page_num]
            normalized_page_content = pages_normalized_text[target_page_num]

            # Extraire le texte matché
            alignment = fuzz.partial_ratio_alignment(
                normalized_snippet,
                normalized_page_content,
                score_cutoff=80
            )

            if not alignment:
                logger.warning(f"      ⚠️  Cannot extract matched text - creating page-level anchor")
                logger.warning("=" * 80)
                logger.warning("      >>> DIAGNOSTIC: CANNOT EXTRACT MATCHED TEXT <<<")
                logger.warning("-" * 80)
                logger.warning(f"      [Is table]: {is_table}")
                logger.warning("-" * 80)
                logger.warning(f"      [Snippet ORIGINAL] (length: {len(search_snippet_for_logs)}):")
                logger.warning("-" * 80)
                logger.warning(search_snippet_for_logs)
                logger.warning("-" * 80)
                logger.warning(f"      [Snippet NORMALIZED] (length: {len(normalized_snippet)}):")
                logger.warning("-" * 80)
                logger.warning(normalized_snippet)
                logger.warning("-" * 80)
                logger.warning(f"      [Page {target_page_num + 1} ORIGINAL] (length: {len(page_text_content)}):")
                logger.warning("-" * 80)
                logger.warning(page_text_content[:500])
                logger.warning("-" * 80)
                logger.warning(
                    f"      [Page {target_page_num + 1} NORMALIZED] (length: {len(normalized_page_content)}):")
                logger.warning("-" * 80)
                logger.warning(normalized_page_content[:500])
                logger.warning("=" * 80)

                dest_name = f"node_{node.id_}"
                toc.append([1, dest_name, target_page_num + 1])
                node.metadata.update({
                    'node_anchor_id': dest_name,
                    'page_number': target_page_num + 1,
                    'page_confidence': best_page_score,
                    'anchor_type': 'page_level',
                    'is_table': is_table
                })
                annotated_count += 1
                last_found_page = target_page_num
                continue

            matched_text_from_pdf = page_text_content[alignment.dest_start: alignment.dest_end]
            logger.info(
                f"      📝 Extracted from PDF ({len(matched_text_from_pdf)} chars): '{matched_text_from_pdf[:100]}...'")

            # Recherche des coordonnées
            text_instances = None
            final_page_num = -1
            strategy_used = None

            text_instances, strategy_used = _find_coords_on_page(doc, target_page_num, matched_text_from_pdf)
            if text_instances:
                final_page_num = target_page_num

            # Fallback : page suivante
            if not text_instances and (target_page_num + 1) < len(doc):
                logger.info(f"      -> Trying next page for coords...")
                text_instances, strategy_used = _find_coords_on_page(doc, target_page_num + 1, matched_text_from_pdf)
                if text_instances:
                    final_page_num = target_page_num + 1
                    logger.info(f"      -> Found on fallback page {final_page_num + 1}!")

            # Créer la destination
            if text_instances:
                dest_name = f"node_{node.id_}"
                toc.append([1, dest_name, final_page_num + 1])
                node.metadata.update({
                    'node_anchor_id': dest_name,
                    'page_number': final_page_num + 1,
                    'page_confidence': best_page_score,
                    'anchor_strategy': strategy_used,
                    'is_table': is_table
                })
                annotated_count += 1
                logger.info(f"      ✅ Destination created on page {final_page_num + 1} (strategy: {strategy_used})")
                last_found_page = final_page_num
            else:
                logger.warning(f"      ⚠️  All coord strategies failed - creating page-level anchor")
                dest_name = f"node_{node.id_}"
                toc.append([1, dest_name, target_page_num + 1])
                node.metadata.update({
                    'node_anchor_id': dest_name,
                    'page_number': target_page_num + 1,
                    'page_confidence': best_page_score,
                    'anchor_type': 'page_level',
                    'is_table': is_table
                })
                annotated_count += 1
                last_found_page = target_page_num

        if annotated_count > 0:
            doc.set_toc(toc)
            doc.save(pdf_path, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
            logger.info(f"\n   ✅ PDF saved with {annotated_count} destinations.")

        doc.close()
        return annotated_count

    except Exception as e:
        logger.error(f"   ❌ Error: {e}", exc_info=True)
        return 0



def run_indexing_logic(source_md_dir: str, index_dir: str):
    """
    Main indexing logic with progress bars.
    """
    from tqdm import tqdm

    logger.info(f"Starting LlamaIndex indexing for directory: {source_md_dir}")
    init_settings()

    # ========================================
    # ÉTAPE 1 : PARSING (création des tiny nodes)
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("ÉTAPE 1 : PARSING DU MARKDOWN (HIÉRARCHIQUE)")
    logger.info("=" * 80)

    parser_only_pipeline = IngestionPipeline(
        transformations=[
            MarkdownNodeParser(include_metadata=True, include_prev_next_rel=True),
        ]
    )

    # ✅ Lecture récursive avec required_exts
    reader = SimpleDirectoryReader(
        input_dir=source_md_dir,
        required_exts=[".md"],
        recursive=True,
        exclude=["*.meta", "*metadata.json"]
    )

    logger.info("📂 Loading documents...")
    all_docs = reader.load_data(show_progress=True)  # Built-in progress bar

    documents = [
        doc for doc in all_docs
        if not doc.metadata.get("file_name", "").endswith(".meta")
           and doc.metadata.get("file_name", "").lower() not in ["metadata.json"]
    ]

    logger.info(f"📁 Enriching {len(documents)} documents with .meta information...")

    # Progress bar for metadata enrichment
    for doc in tqdm(documents, desc="Enriching metadata", unit="doc"):
        md_filename = doc.metadata.get("file_name", "")

        if md_filename:
            md_filepath = doc.metadata.get("file_path", "")

            if md_filepath:
                meta_filepath = md_filepath + ".meta"
            else:
                meta_filepath = find_meta_file_in_tree(source_md_dir, md_filename)

            if meta_filepath and os.path.exists(meta_filepath):
                meta_info = load_metadata_from_meta_file_direct(meta_filepath)

                if "source_url" in meta_info:
                    doc.metadata["source_url"] = meta_info["source_url"]

                if "source_filename" in meta_info:
                    doc.metadata["source_filename"] = meta_info["source_filename"]

                if "source_relative_path" in meta_info:
                    doc.metadata["source_relative_path"] = meta_info["source_relative_path"]

    logger.info(f"📄 {len(documents)} documents loaded and enriched")

    logger.info("🔨 Parsing documents into nodes...")
    tiny_nodes = parser_only_pipeline.run(documents=documents, show_progress=True)
    logger.info(f"📦 {len(tiny_nodes)} tiny nodes créés")

    # ========================================
    # ÉTAPE 2 : FILTRAGE ET FUSION
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("ÉTAPE 2 : FILTRAGE ET FUSION")
    logger.info("=" * 80)

    # ========================================
    # ÉTAPE 2 : FILTRAGE ET FUSION (FIXED)
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("ÉTAPE 2 : FILTRAGE ET FUSION (BATCHED)")
    logger.info("=" * 80)

    # ✅ FIX 1: Add disable_cache=True to prevent MemoryError in get_transformation_hash
    processing_pipeline = IngestionPipeline(
        transformations=[
            FilterTableOfContentsWithLLM(),
            MergeSmallNodes(
                tiny_size=200,
                child_min_size=1000,
                child_max_size=2000,
                parent_min_size=2000,
                parent_max_size=5000
            ),
            RepairRelationships(),
        ],
        disable_cache=True  # <--- CRITICAL: Prevents hash calculation crash
    )

    logger.info("⚙️  Processing nodes in batches to save memory...")

    # ✅ FIX 2: Process in batches (e.g., 50,000 nodes at a time)
    # This prevents holding 300k processed nodes in RAM during the pipeline run
    BATCH_SIZE = 50000
    all_nodes = []

    total_batches = (len(tiny_nodes) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(tiny_nodes), BATCH_SIZE):
        batch_idx = (i // BATCH_SIZE) + 1
        batch_nodes = tiny_nodes[i: i + BATCH_SIZE]

        logger.info(f"   🔄 Processing Batch {batch_idx}/{total_batches} ({len(batch_nodes)} nodes)...")

        # Run pipeline on this batch
        processed_batch = processing_pipeline.run(nodes=batch_nodes, show_progress=True)
        all_nodes.extend(processed_batch)

        # Optional: Manual garbage collection between batches
        import gc
        del batch_nodes
        del processed_batch
        gc.collect()

    logger.info(f"📦 {len(all_nodes)} nodes après traitement (Total)")

    # ========================================
    # ÉTAPE 3 : ANNOTATION POST-FUSION
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("ÉTAPE 3 : ANNOTATION DES DOCUMENTS (POST-FUSION, HIÉRARCHIQUE)")
    logger.info("=" * 80)

    source_files_archive = os.path.join(os.path.dirname(source_md_dir), "source_files_archive")

    annotate_documents_with_node_anchors(
        all_nodes,
        source_files_archive,
        source_md_dir
    )

    # ========================================
    # ÉTAPE 4 : SÉPARATION CHILD/PARENT NODES
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("ÉTAPE 4 : SÉPARATION CHILD/PARENT NODES")
    logger.info("=" * 80)

    child_nodes = []
    parent_nodes = []
    for node in all_nodes:
        if NodeRelationship.PARENT in node.relationships:
            child_nodes.append(node)
        else:
            parent_nodes.append(node)

    logger.info(f"📊 Hiérarchie créée:")
    logger.info(f"  • Child nodes (1000-2000 chars): {len(child_nodes)}")
    logger.info(f"  • Parent nodes (2000-5000 chars): {len(parent_nodes)}")

    # ÉTAPE 5 : SUB-CHUNKS
    logger.info("\n" + "=" * 80)
    logger.info("ÉTAPE 5 : CRÉATION DES SUB-CHUNKS")
    logger.info("=" * 80)

    child_splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
    sub_chunks = []

    for child_node in tqdm(child_nodes, desc="Creating sub-chunks", unit="node"):
        chunks = child_splitter.get_nodes_from_documents([child_node])
        for chunk in chunks:
            chunk.relationships[NodeRelationship.PARENT] = RelatedNodeInfo(node_id=child_node.id_)
            chunk.metadata.update({
                k: v for k, v in child_node.metadata.items()
                if k.startswith("Header") or k in [
                    "header_path", "file_name", "source_url",
                    "node_anchor_id", "source_relative_path",
                    "page_number", "page_confidence",
                    "html_confidence"
                ]
            })
            sub_chunks.append(chunk)

    logger.info(f"  • Sub-chunks créés: {len(sub_chunks)}")

    # ÉTAPE 6 : INDEXATION
    logger.info("\n" + "=" * 80)
    logger.info("ÉTAPE 6 : INDEXATION FAISS + EMBEDDINGS")
    logger.info("=" * 80)

    d = 4096
    faiss_index = faiss.IndexFlatL2(d)
    vector_store = FaissVectorStore(faiss_index=faiss_index)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    all_nodes_for_docstore = sub_chunks + child_nodes + parent_nodes
    storage_context.docstore.add_documents(all_nodes_for_docstore)

    logger.info(f"📦 Docstore:")
    logger.info(f"  • Sub-chunks (embedding): {len(sub_chunks)}")
    logger.info(f"  • Child nodes: {len(child_nodes)}")
    logger.info(f"  • Parent nodes: {len(parent_nodes)}")
    logger.info(f"  • TOTAL: {len(all_nodes_for_docstore)}")

    logger.info(f"\n🚀 Creating embeddings for {len(sub_chunks)} sub-chunks...")
    logger.info(f"   (This is the slowest step - calling embedding API)")

    index = VectorStoreIndex(
        nodes=sub_chunks,
        storage_context=storage_context,
        show_progress=True  # Built-in progress for embeddings
    )

    logger.info("💾 Persisting index to disk...")
    index.storage_context.persist(persist_dir=index_dir)

    logger.info(f"\n{'=' * 80}")
    logger.info(f"✅ INDEXATION COMPLÈTE (STRUCTURE HIÉRARCHIQUE PRÉSERVÉE)")
    logger.info(f"{'=' * 80}\n")



