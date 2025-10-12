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
import pymupdf  # pip install pymupdf
from rapidfuzz import fuzz
from bs4 import BeautifulSoup
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
import pymupdf  # pip install pymupdf
from rapidfuzz import fuzz
from bs4 import BeautifulSoup

from src.core.indexing_html import _annotate_html_with_anchors, clean_html_before_docling

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


# src/core/indexing.py

def annotate_documents_with_node_anchors(
        nodes: List,
        source_files_archive: str,
        md_files_dir: str
) -> List:
    """
    Modifie les documents sources (PDF/HTML) pour insérer des ancres/destinations
    pointant vers chaque child node.

    Pour PDF : Ajoute des destinations nommées
    Pour HTML : Ajoute des IDs aux headers et crée un fichier *_indexed.html
    """
    logger.info(f"\n{'=' * 80}")
    logger.info(f"ANNOTATION DES DOCUMENTS AVEC ANCRES DE NODES")
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
        meta_file = os.path.join(md_files_dir, f"{md_filename}.meta")
        if not os.path.exists(meta_file):
            logger.warning(f"⚠️ Métadonnées introuvables pour {md_filename}")
            total_failed += len(doc_nodes)
            continue

        with open(meta_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        source_filename = metadata.get("source_filename", "")
        if not source_filename:
            logger.warning(f"⚠️ Nom de fichier source manquant pour {md_filename}")
            total_failed += len(doc_nodes)
            continue

        source_path = os.path.join(source_files_archive, source_filename)
        if not os.path.exists(source_path):
            logger.warning(f"⚠️ Fichier source introuvable : {source_path}")
            total_failed += len(doc_nodes)
            continue

        # Séparer child nodes (à annoter) et parent nodes (à skipper)
        child_nodes = [n for n in doc_nodes if NodeRelationship.PARENT in n.relationships]
        parent_nodes = [n for n in doc_nodes if NodeRelationship.PARENT not in n.relationships]

        logger.info(f"\n📄 Traitement de {source_filename}")
        logger.info(f"   • {len(child_nodes)} child nodes à annoter")
        logger.info(f"   • {len(parent_nodes)} parent nodes (seront ignorés, recevront un ID d'ancre de fallback)")

        # Parent nodes : ID de fallback
        for parent in parent_nodes:
            parent.metadata['node_anchor_id'] = f"node_{parent.id_}"
        total_skipped_parents += len(parent_nodes)

        nodes_to_annotate = child_nodes

        _, ext = os.path.splitext(source_filename)
        ext_lower = ext.lower()

        if nodes_to_annotate:
            if ext_lower == '.pdf':
                # Annotation PDF (existant)
                annotated = _annotate_pdf_with_destinations(nodes_to_annotate, source_path)
                total_annotated += annotated
                total_failed += (len(nodes_to_annotate) - annotated)

            elif ext_lower in ['.html', '.htm']:
                # ✨ Annotation HTML (nouvelle version avec modification du fichier)
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
    logger.info(f"  ⏭️  Parent nodes (ignorés) : {total_skipped_parents}")
    logger.info(f"  ❌ Échecs : {total_failed}")
    logger.info(f"{'=' * 80}\n")

    return nodes


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
    logger.info(f"Starting LlamaIndex indexing for directory: {source_md_dir}")
    init_settings()

    # ========================================
    # ÉTAPE 1 : PARSING (création des tiny nodes)
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("ÉTAPE 1 : PARSING DU MARKDOWN")
    logger.info("=" * 80)

    parser_only_pipeline = IngestionPipeline(
        transformations=[
            MarkdownNodeParser(include_metadata=True, include_prev_next_rel=True),
        ]
    )
    reader = SimpleDirectoryReader(source_md_dir)
    all_docs = reader.load_data()
    documents = [
        doc for doc in all_docs
        if not doc.metadata.get("file_name", "").endswith(".meta")
    ]
    logger.info(f"📝 Enriching documents with .meta information...")
    for doc in documents:
        md_filename = doc.metadata.get("file_name", "")

        if md_filename:
            md_filepath = os.path.join(source_md_dir, md_filename)
            meta_info = load_metadata_from_meta_file(md_filepath)

            if "source_url" in meta_info:
                doc.metadata["source_url"] = meta_info["source_url"]
                logger.debug(f"  ✓ source_url: {meta_info['source_url']}")

            if "source_filename" in meta_info:
                doc.metadata["source_filename"] = meta_info["source_filename"]

    logger.info(f"📄 {len(documents)} documents loaded and enriched")

    logger.info(f"📄 {len(documents)} documents markdown chargés (fichiers .meta exclus)")
    tiny_nodes = parser_only_pipeline.run(documents=documents)
    logger.info(f"📦 {len(tiny_nodes)} tiny nodes créés")

    # ========================================
    # ÉTAPE 2 : FILTRAGE ET FUSION
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("ÉTAPE 2 : FILTRAGE ET FUSION")
    logger.info("=" * 80)

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
        ]
    )
    all_nodes = processing_pipeline.run(nodes=tiny_nodes)

    # ========================================
    # ÉTAPE 3 : ANNOTATION POST-FUSION
    # ========================================
    # ▼▼▼ BLOC DÉPLACÉ ET MODIFIÉ ▼▼▼
    logger.info("\n" + "=" * 80)
    logger.info("ÉTAPE 3 : ANNOTATION DES DOCUMENTS (POST-FUSION)")
    logger.info("=" * 80)
    logger.info("Annotation basée sur les child nodes pour une meilleure précision.")

    source_files_archive = os.path.join(os.path.dirname(source_md_dir), "source_files_archive")


    # On passe tous les noeuds (child+parent) à la fonction d'annotation.
    # Elle saura les différencier et n'annotera que les child nodes.
    annotate_documents_with_node_anchors(
        all_nodes,
        source_files_archive,
        source_md_dir
    )
    # ▲▲▲ FIN DU BLOC MODIFIÉ ▲▲▲

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

    # ========================================
    # ÉTAPE 5 : CRÉATION DES SUB-CHUNKS
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("ÉTAPE 5 : CRÉATION DES SUB-CHUNKS")
    logger.info("=" * 80)

    child_splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
    sub_chunks = []
    for child_node in child_nodes:
        chunks = child_splitter.get_nodes_from_documents([child_node])
        for chunk in chunks:
            chunk.relationships[NodeRelationship.PARENT] = RelatedNodeInfo(node_id=child_node.id_)
            chunk.metadata.update({
                k: v for k, v in child_node.metadata.items()
                if k.startswith("Header") or k in [
                    "header_path", "file_name", "source_url",
                    "node_anchor_id",
                    "page_number", "page_confidence",
                    "html_confidence"
                ]
            })
            sub_chunks.append(chunk)

    logger.info(f"  • Sub-chunks créés: {len(sub_chunks)}")

    # ========================================
    # ÉTAPE 6 : INDEXATION
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("ÉTAPE 6 : INDEXATION FAISS")
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

    index = VectorStoreIndex(nodes=sub_chunks, storage_context=storage_context)
    index.storage_context.persist(persist_dir=index_dir)

    # ========================================
    # RÉSUMÉ FINAL
    # ========================================
    logger.info(f"\n{'=' * 80}")
    logger.info(f"✅ INDEXATION COMPLÈTE")
    logger.info(f"{'=' * 80}")
    logger.info(f"  • Vector index: {len(sub_chunks)} sub-chunks indexés")
    logger.info(f"  • Docstore: {len(all_nodes_for_docstore)} nodes stockés")
    logger.info(f"  • Hiérarchie: sub-chunk → child → parent")
    logger.info(f"  • Documents annotés avec ancres de navigation ✨")
    # Message mis à jour pour refléter la nouvelle logique
    logger.info(f"  • Annotation effectuée sur les child nodes (post-fusion) pour plus de robustesse.")
    logger.info(f"{'=' * 80}\n")


import time


def index_creation_task(index_id: str, files_info: List[dict], metadata_json: str):
    """
    Tâche d'indexation complète :
    1. Archivage des fichiers sources
    2. Nettoyage HTML (si applicable)
    3. Conversion via Docling
    4. Création des fichiers .meta
    5. Indexation LlamaIndex avec enrichissement des métadonnées
    """
    index_path = get_index_path(index_id)
    md_files_dir = os.path.join(index_path, "md_files")
    index_dir = os.path.join(index_path, "index")
    source_files_archive = os.path.join(index_path, "source_files_archive")
    source_files_temp = os.path.join(index_path, "source_files")

    # ✅ Créer un fichier de statut "en cours"
    status_file = os.path.join(index_path, ".indexing_status")
    start_time = time.time()
    with open(status_file, "w") as f:
        json.dump({"status": "in_progress", "started_at": start_time}, f)

    os.makedirs(md_files_dir, exist_ok=True)
    os.makedirs(source_files_archive, exist_ok=True)

    try:
        metadata = json.loads(metadata_json) if metadata_json else {}
        seen_basenames = set()

        # ========================================
        # PHASE 1 : CONVERSION DES FICHIERS
        # ========================================
        for file_info in files_info:
            file_path = file_info["path"]  # Depuis source_files (temp)
            original_filename = file_info["filename"]
            normalized_basename, ext = os.path.splitext(normalize_filename(original_filename))

            # Vérifier doublons
            if normalized_basename in seen_basenames:
                raise ValueError(f"Duplicate filename: {normalized_basename}")
            seen_basenames.add(normalized_basename)

            # ✅ Copier vers source_files_archive (permanent)
            archived_filename = f"{normalized_basename}{ext}"
            archive_destination = os.path.join(source_files_archive, archived_filename)

            if file_path != archive_destination:
                shutil.copy2(file_path, archive_destination)
                logger.info(f"File archived: {archived_filename} → source_files_archive")

            # Préparer les chemins de sortie
            md_filename = f"{normalized_basename}.md"
            md_filepath = os.path.join(md_files_dir, md_filename)
            meta_filepath = os.path.join(md_files_dir, f"{md_filename}.meta")

            # Créer le fichier .meta s'il n'existe pas
            if not os.path.exists(meta_filepath):
                source_url = metadata.get(original_filename, "URL not provided")
                with open(meta_filepath, "w", encoding="utf-8") as f:
                    json.dump({
                        "source_url": source_url,
                        "source_filename": archived_filename
                    }, f)
                logger.info(f"Metadata file created: {os.path.basename(meta_filepath)}")

            # Skip si le markdown existe déjà
            if os.path.exists(md_filepath):
                logger.info(f"Markdown '{md_filename}' exists, skipping Docling")
                continue

            # ✨ Nettoyer le HTML avant Docling si c'est un fichier HTML
            if ext.lower() in ['.html', '.htm']:
                logger.info(f"📄 Fichier HTML détecté: {original_filename}")
                try:
                    cleaned_html_path = clean_html_before_docling(archive_destination)
                    file_to_convert = cleaned_html_path
                    cleanup_temp = True
                except Exception as e:
                    logger.warning(f"⚠️ Échec du nettoyage HTML, utilisation du fichier original: {e}")
                    file_to_convert = archive_destination
                    cleanup_temp = False
            else:
                file_to_convert = archive_destination
                cleanup_temp = False

            # Conversion via Docling
            logger.info(f"Converting file '{original_filename}' via Docling...")
            try:
                with open(file_to_convert, "rb") as f:
                    response = requests.post(
                        DOCLING_URL,
                        files={'files': (original_filename, f)},
                        data={"table_mode": "accurate"},
                    )
                    response.raise_for_status()
            except requests.exceptions.RequestException as req_err:
                logger.error(f"Docling connection error for '{original_filename}': {req_err}")
                if cleanup_temp and os.path.exists(file_to_convert):
                    os.remove(file_to_convert)
                continue
            finally:
                # Nettoyer le fichier temporaire
                if cleanup_temp and os.path.exists(file_to_convert):
                    os.remove(file_to_convert)
                    logger.debug(f"   🗑️  Fichier temporaire supprimé")

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

            # Sauvegarder le Markdown
            with open(md_filepath, "w", encoding="utf-8") as f:
                f.write(cleaned_md)
            logger.info(f"✓ Markdown saved: {md_filename}")

        # ========================================
        # PHASE 2 : INDEXATION LLAMAINDEX
        # ========================================
        logger.info(f"Starting LlamaIndex indexing for directory: {md_files_dir}")
        init_settings()

        # Charger tous les documents markdown
        md_reader = SimpleDirectoryReader(
            input_dir=md_files_dir,
            required_exts=[".md"],
            exclude=["*.meta"],
            recursive=False
        )
        documents = md_reader.load_data()

        # ✨ ENRICHIR chaque document avec les métadonnées du fichier .meta
        logger.info(f"📝 Enriching documents with .meta information...")
        for doc in documents:
            md_filename = doc.metadata.get("file_name", "")

            if md_filename:
                md_filepath = os.path.join(md_files_dir, md_filename)
                meta_info = load_metadata_from_meta_file(md_filepath)

                # Ajouter source_url
                if "source_url" in meta_info:
                    doc.metadata["source_url"] = meta_info["source_url"]
                    logger.info(f"  ✓ Added source_url for {md_filename}: {meta_info['source_url']}")
                else:
                    logger.info(f"  ⚠️  source_url missing in .meta for {md_filename}")

                # Ajouter source_filename
                if "source_filename" in meta_info:
                    doc.metadata["source_filename"] = meta_info["source_filename"]

        logger.info(f"📄 {len(documents)} documents loaded and enriched")

        # Lancer l'indexation
        run_indexing_logic(source_md_dir=md_files_dir, index_dir=index_dir)

        # ✅ Marquer comme terminé avec succès
        end_time = time.time()
        with open(status_file, "w") as f:
            json.dump({
                "status": "completed",
                "started_at": start_time,
                "completed_at": end_time,
                "duration_seconds": end_time - start_time,
                "num_documents": len(files_info)
            }, f)

        logger.info(f"✅ Indexation terminée avec succès pour {index_id} en {end_time - start_time:.1f}s")

    except Exception as e:
        # ✅ Marquer comme échoué
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


def load_metadata_from_meta_file(md_filepath: str) -> dict:
    """
    Charge les métadonnées depuis le fichier .meta correspondant au markdown.

    Args:
        md_filepath: Chemin vers le fichier .md

    Returns:
        Dict avec les métadonnées, ou {} si pas de fichier .meta
    """
    meta_filepath = md_filepath + ".meta"

    if not os.path.exists(meta_filepath):
        return {}

    try:
        with open(meta_filepath, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        return metadata
    except Exception as e:
        logger.warning(f"Failed to load .meta file {meta_filepath}: {e}")
        return {}