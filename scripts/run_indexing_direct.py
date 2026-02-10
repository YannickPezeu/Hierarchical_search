#!/usr/bin/env python3
"""
run_indexing_direct.py - Index directly from existing md_files (no API)

Use this when you already have markdown files (e.g., from RCP/Docling)
and just need to build the vector index.

Usage:
    python -m scripts.run_indexing_direct large_campus2
    python -m scripts.run_indexing_direct large_campus2 --dry-run
"""

import os
import sys
import json
import time
import logging
import argparse
import shutil
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from src.core.config import ALL_INDEXES_DIR
from src.core.cache import search_cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)




def run_indexing_from_md(index_id: str, dry_run: bool = False) -> bool:
    """
    Run indexing directly from existing md_files directory.
    
    This bypasses the API and Docling conversion - use when md_files already exist.
    """
    index_path = os.path.join(ALL_INDEXES_DIR, index_id)
    md_files_dir = os.path.join(index_path, "md_files")
    index_dir = os.path.join(index_path, "index")
    status_file = os.path.join(index_path, ".indexing_status")
    
    # Validate
    if not os.path.exists(index_path):
        logger.error(f"Index path does not exist: {index_path}")
        return False
    
    if not os.path.exists(md_files_dir):
        logger.error(f"md_files directory does not exist: {md_files_dir}")
        return False
    
    # Count MD files
    md_files = list(Path(md_files_dir).rglob("*.md"))
    meta_files = list(Path(md_files_dir).rglob("*.meta"))
    
    logger.info(f"📁 Found {len(md_files)} markdown files")
    logger.info(f"📋 Found {len(meta_files)} meta files")
    
    if len(md_files) == 0:
        logger.error("No markdown files found!")
        return False
    
    if dry_run:
        logger.info("\n" + "=" * 60)
        logger.info("DRY RUN - Would perform:")
        logger.info("=" * 60)
        logger.info(f"  1. Clear cache for: {index_id}")
        logger.info(f"  2. Delete existing index: {index_dir}")
        logger.info(f"  3. Run LlamaIndex on {len(md_files)} files")
        logger.info("=" * 60)
        return True
    
    # Import heavy modules only when needed
    from src.core.indexing import run_indexing_logic
    
    start_time = time.time()
    
    # Update status
    with open(status_file, "w") as f:
        json.dump({
            "status": "in_progress",
            "started_at": start_time,
            "mode": "direct_from_md"
        }, f)
    
    try:
        # Clear cache
        logger.info(f"🗑️  Clearing cache for: {index_id}")
        search_cache.clear_index_cache(index_path)
        
        # Delete existing index
        if os.path.exists(index_dir):
            logger.info(f"🗑️  Removing existing index...")
            shutil.rmtree(index_dir)
        
        # Run indexing
        logger.info(f"\n{'='*60}")
        logger.info("STARTING LLAMAINDEX INDEXING")
        logger.info(f"{'='*60}\n")
        
        run_indexing_logic(source_md_dir=md_files_dir, index_dir=index_dir)
        
        # Update status
        end_time = time.time()
        duration = end_time - start_time
        
        with open(status_file, "w") as f:
            json.dump({
                "status": "completed",
                "started_at": start_time,
                "completed_at": end_time,
                "duration_seconds": round(duration, 2),
                "num_documents": len(md_files),
                "mode": "direct_from_md"
            }, f)
        
        logger.info(f"\n{'='*60}")
        logger.info("✅ INDEXING COMPLETE")
        logger.info(f"   Duration: {duration:.1f}s")
        logger.info(f"   Documents: {len(md_files)}")
        logger.info(f"{'='*60}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Indexing failed: {e}", exc_info=True)
        
        with open(status_file, "w") as f:
            json.dump({
                "status": "failed",
                "started_at": start_time,
                "failed_at": time.time(),
                "error": str(e),
                "mode": "direct_from_md"
            }, f)
        
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Index directly from existing md_files (bypasses API/Docling)"
    )
    
    parser.add_argument("index_id", help="Index identifier (e.g., large_campus2)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info(f"DIRECT INDEXING: {args.index_id}")
    logger.info("(from existing md_files, no API/Docling)")
    logger.info("=" * 60)
    
    success = run_indexing_from_md(args.index_id, dry_run=args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
