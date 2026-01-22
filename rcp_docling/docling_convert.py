#!/usr/bin/env python3
"""
docling_convert.py - Conversion batch avec support GPU et correctifs d'imports
"""

import os
import sys
import logging
import traceback
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# === CONFIGURATION ===
INPUT_DIR = os.getenv("INPUT_DIR", "/data/input")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/data/output")
REPORT_FILE = os.getenv("REPORT_FILE", "/data/conversion_report.txt")

SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.pptx', '.html', '.htm', '.xlsx', '.png', '.jpg', '.jpeg'}


def find_documents(input_dir: str) -> list[Path]:
    documents = []
    input_path = Path(input_dir)
    if not input_path.exists():
        logger.error(f"❌ Input directory not found: {input_dir}")
        return []
    for ext in SUPPORTED_EXTENSIONS:
        documents.extend(input_path.rglob(f"*{ext}"))
        documents.extend(input_path.rglob(f"*{ext.upper()}"))
    seen = set()
    unique_docs = []
    for doc in documents:
        doc_lower = str(doc).lower()
        if doc_lower not in seen:
            seen.add(doc_lower)
            unique_docs.append(doc)
    return sorted(unique_docs)


def convert_document(converter, input_file: Path, output_file: Path) -> tuple[bool, str]:
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        # Conversion
        result = converter.convert(str(input_file))
        markdown_content = result.document.export_to_markdown()

        if not markdown_content or len(markdown_content.strip()) < 10:
            return False, "Empty output"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        return True, f"{len(markdown_content)} chars"
    except Exception as e:
        return False, str(e)[:100]


def main():
    logger.info("=" * 60)
    logger.info("🚀 Docling Batch Converter (GPU Enabled) - Starting")
    logger.info("=" * 60)

    # --- Chargement Docling avec GPU ---
    logger.info("⏳ Loading Docling components...")
    try:
        # IMPORTS IMPORTANTS : Doivent être faits AVANT l'utilisation
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.pipeline_options import PdfPipelineOptions, AcceleratorOptions, AcceleratorDevice
        from docling.datamodel.base_models import InputFormat

        # Configurer le pipeline pour utiliser CUDA (GPU)
        pipeline_options = PdfPipelineOptions()
        pipeline_options.accelerator_options = AcceleratorOptions(
            num_threads=8,
            device=AcceleratorDevice.CUDA  # Force le GPU
        )

        # Initialiser le convertisseur
        # InputFormat est maintenant correctement défini grâce aux imports ci-dessus
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        logger.info("✅ Docling loaded successfully with CUDA/GPU support")

    except Exception as e:
        logger.error(f"❌ Failed to load Docling: {e}")
        traceback.print_exc()
        sys.exit(1)

    # --- Suite du script standard ---
    documents = find_documents(INPUT_DIR)
    if not documents:
        logger.warning("⚠️ No documents found!")
        sys.exit(0)

    logger.info(f"📄 Found {len(documents)} document(s)")

    stats = {"success": 0, "failed": 0, "skipped": 0}
    report_lines = [f"Report {datetime.now().isoformat()}", "-" * 60]

    input_path = Path(INPUT_DIR)
    output_path = Path(OUTPUT_DIR)

    for doc in tqdm(documents, desc="Converting"):
        relative_path = doc.relative_to(input_path)
        output_file = output_path / relative_path.with_suffix('.md')

        if output_file.exists():
            stats["skipped"] += 1
            continue

        success, msg = convert_document(converter, doc, output_file)
        status = "OK" if success else "FAIL"
        if success:
            stats["success"] += 1
            logger.info(f"✅ {relative_path}")
        else:
            stats["failed"] += 1
            logger.error(f"❌ {relative_path}: {msg}")

        report_lines.append(f"{status} | {relative_path} | {msg}")

    # Final Report
    logger.info("=" * 60)
    logger.info(f"Finished: {stats['success']} OK, {stats['failed']} Fail")

    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))


if __name__ == "__main__":
    main()