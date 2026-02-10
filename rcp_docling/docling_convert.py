#!/usr/bin/env python3
"""
docling_convert.py - Conversion batch avec support GPU et gestion des images

CHANGELOG v2.0:
- Added IMAGE_MODE env var to control image handling (placeholder/referenced/embedded)
- Added SKIP_IMAGES env var to completely disable image extraction
- Prevents 10GB+ markdown files from base64-encoded images
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

# === IMAGE HANDLING OPTIONS ===
# IMAGE_MODE: "placeholder" (default) | "referenced" | "embedded"
#   - placeholder: Just shows <!-- image --> (smallest files, text-only)
#   - referenced:  Saves images to separate files, links them in markdown
#   - embedded:    Base64 inline (WARNING: can create 10GB+ files!)
IMAGE_MODE = os.getenv("IMAGE_MODE", "placeholder").lower()

# SKIP_IMAGES: "true" | "false" - Skip image extraction entirely (fastest)
SKIP_IMAGES = os.getenv("SKIP_IMAGES", "false").lower() == "true"

# IMAGE_SCALE: Scale factor for extracted images (only if referenced mode)
IMAGE_SCALE = float(os.getenv("IMAGE_SCALE", "1.0"))

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


def convert_document(converter, input_file: Path, output_file: Path, image_ref_mode) -> tuple[bool, str]:
    """Convert a single document to markdown."""
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Conversion
        result = converter.convert(str(input_file))

        # Export with image mode control
        markdown_content = result.document.export_to_markdown(
            image_mode=image_ref_mode
        )

        if not markdown_content or len(markdown_content.strip()) < 10:
            return False, "Empty output"

        # Check file size before writing (safety check)
        content_size_mb = len(markdown_content.encode('utf-8')) / (1024 * 1024)
        if content_size_mb > 100:  # Warn if > 100MB
            logger.warning(f"⚠️ Large output: {content_size_mb:.1f}MB for {input_file.name}")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        return True, f"{len(markdown_content)} chars ({content_size_mb:.2f}MB)"
    except Exception as e:
        return False, str(e)[:100]


def main():
    logger.info("=" * 60)
    logger.info("🚀 Docling Batch Converter (GPU + Image Control) - Starting")
    logger.info("=" * 60)

    # --- Chargement Docling avec GPU ---
    logger.info("⏳ Loading Docling components...")
    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.pipeline_options import PdfPipelineOptions, AcceleratorOptions, AcceleratorDevice
        from docling.datamodel.base_models import InputFormat
        from docling_core.types.doc import ImageRefMode

        # Map IMAGE_MODE string to enum
        image_mode_map = {
            "placeholder": ImageRefMode.PLACEHOLDER,
            "referenced": ImageRefMode.REFERENCED,
            "embedded": ImageRefMode.EMBEDDED,
        }

        if IMAGE_MODE not in image_mode_map:
            logger.warning(f"⚠️ Unknown IMAGE_MODE '{IMAGE_MODE}', defaulting to 'placeholder'")
            image_ref_mode = ImageRefMode.PLACEHOLDER
        else:
            image_ref_mode = image_mode_map[IMAGE_MODE]

        logger.info(f"📸 Image mode: {IMAGE_MODE.upper()}")
        logger.info(f"🖼️ Skip image extraction: {SKIP_IMAGES}")

        # Configure pipeline
        pipeline_options = PdfPipelineOptions()
        pipeline_options.accelerator_options = AcceleratorOptions(
            num_threads=8,
            device=AcceleratorDevice.CUDA  # Force GPU
        )

        # Image extraction control
        if SKIP_IMAGES:
            # Don't extract images at all (fastest, smallest output)
            pipeline_options.generate_picture_images = False
            pipeline_options.generate_page_images = False
            logger.info("📸 Image extraction DISABLED")
        else:
            # Extract images but control how they appear in markdown
            pipeline_options.generate_picture_images = (IMAGE_MODE == "referenced")
            pipeline_options.images_scale = IMAGE_SCALE
            if IMAGE_MODE == "referenced":
                logger.info(f"📸 Images will be saved separately (scale: {IMAGE_SCALE})")

        # Initialize converter
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

    # --- Find documents ---
    documents = find_documents(INPUT_DIR)
    if not documents:
        logger.warning("⚠️ No documents found!")
        sys.exit(0)

    logger.info(f"📄 Found {len(documents)} document(s)")

    stats = {"success": 0, "failed": 0, "skipped": 0, "total_size_mb": 0}
    report_lines = [
        f"Conversion Report - {datetime.now().isoformat()}",
        f"Image Mode: {IMAGE_MODE}",
        f"Skip Images: {SKIP_IMAGES}",
        "-" * 60
    ]

    input_path = Path(INPUT_DIR)
    output_path = Path(OUTPUT_DIR)

    for doc in tqdm(documents, desc="Converting"):
        relative_path = doc.relative_to(input_path)
        output_file = output_path / relative_path.with_suffix('.md')

        if output_file.exists():
            stats["skipped"] += 1
            continue

        success, msg = convert_document(converter, doc, output_file, image_ref_mode)
        status = "OK" if success else "FAIL"

        if success:
            stats["success"] += 1
            # Track output size
            if output_file.exists():
                size_mb = output_file.stat().st_size / (1024 * 1024)
                stats["total_size_mb"] += size_mb
            logger.info(f"✅ {relative_path}")
        else:
            stats["failed"] += 1
            logger.error(f"❌ {relative_path}: {msg}")

        report_lines.append(f"{status} | {relative_path} | {msg}")

    # Final Report
    logger.info("=" * 60)
    logger.info(f"✅ Success: {stats['success']}")
    logger.info(f"❌ Failed:  {stats['failed']}")
    logger.info(f"⏭️ Skipped: {stats['skipped']}")
    logger.info(f"📦 Total output size: {stats['total_size_mb']:.2f} MB")
    logger.info("=" * 60)

    report_lines.extend([
        "-" * 60,
        f"Success: {stats['success']}",
        f"Failed: {stats['failed']}",
        f"Skipped: {stats['skipped']}",
        f"Total output size: {stats['total_size_mb']:.2f} MB"
    ])

    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))


if __name__ == "__main__":
    main()