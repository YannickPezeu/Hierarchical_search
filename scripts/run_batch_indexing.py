#!/usr/bin/env python3
"""
run_batch_indexing.py - Batch re-indexation of multiple indexes via API

Usage:
    # Re-index all indexes
    python -m scripts.run_batch_indexing --all
    
    # Re-index specific indexes
    python -m scripts.run_batch_indexing LEX_FR large_campus
    
    # Wait for all to complete
    python -m scripts.run_batch_indexing --all --wait
    
    # Dry run
    python -m scripts.run_batch_indexing --all --dry-run

For cron jobs:
    0 2 * * * cd /path/to/project && /path/to/venv/bin/python -m scripts.run_batch_indexing --all --wait >> /var/log/indexing.log 2>&1
"""

import sys
import time
import logging
import argparse
from pathlib import Path
from typing import List, Dict

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from scripts.run_indexing import (
    list_indexes,
    create_index,
    wait_for_completion,
    get_index_status
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def run_batch(
    index_ids: List[str],
    dry_run: bool = False,
    wait: bool = False,
    stop_on_error: bool = False
) -> Dict[str, dict]:
    """
    Process multiple indexes in sequence.
    
    Args:
        index_ids: List of index identifiers
        dry_run: If True, only show what would be done
        wait: If True, wait for each index to complete before starting next
        stop_on_error: If True, stop on first error
        
    Returns:
        Dict mapping index_id to result info
    """
    results = {}
    total_start = time.time()
    
    logger.info("=" * 70)
    logger.info(f"BATCH INDEXING - {len(index_ids)} indexes")
    logger.info(f"Dry run: {dry_run}")
    logger.info(f"Wait for completion: {wait}")
    logger.info("=" * 70)
    
    for i, index_id in enumerate(index_ids, 1):
        logger.info(f"\n[{i}/{len(index_ids)}] Processing: {index_id}")
        logger.info("-" * 40)
        
        start_time = time.time()
        
        try:
            # Start indexing
            success = create_index(index_id, dry_run=dry_run)
            
            if success and wait and not dry_run:
                # Wait for completion
                success = wait_for_completion(index_id)
            
            duration = time.time() - start_time
            
            results[index_id] = {
                "success": success,
                "duration_seconds": round(duration, 2),
                "error": None
            }
            
            if not success and stop_on_error:
                logger.error(f"Stopping batch due to error in {index_id}")
                break
                
        except Exception as e:
            duration = time.time() - start_time
            results[index_id] = {
                "success": False,
                "duration_seconds": round(duration, 2),
                "error": str(e)
            }
            logger.error(f"Error processing {index_id}: {e}")
            
            if stop_on_error:
                break
    
    total_duration = time.time() - total_start
    
    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("BATCH SUMMARY")
    logger.info("=" * 70)
    
    successful = sum(1 for r in results.values() if r["success"])
    failed = len(results) - successful
    
    logger.info(f"Total indexes: {len(index_ids)}")
    logger.info(f"Processed: {len(results)}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Total duration: {total_duration:.1f} seconds")
    
    if failed > 0:
        logger.info("\nFailed indexes:")
        for idx_id, result in results.items():
            if not result["success"]:
                logger.info(f"  ❌ {idx_id}: {result.get('error', 'Unknown error')}")
    
    logger.info("=" * 70)
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Batch re-indexation via API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Re-index all
  python -m scripts.run_batch_indexing --all
  
  # Re-index specific indexes
  python -m scripts.run_batch_indexing LEX_FR large_campus
  
  # Wait for completion
  python -m scripts.run_batch_indexing --all --wait
  
  # Dry run
  python -m scripts.run_batch_indexing --all --dry-run

Note: API server must be running (python -m src.main)
"""
    )
    
    parser.add_argument("index_ids", nargs="*", help="Index identifiers")
    parser.add_argument("--all", action="store_true", help="Process all indexes")
    parser.add_argument("--wait", "-w", action="store_true", help="Wait for each to complete")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop on first error")
    parser.add_argument("--exclude", nargs="+", default=[], help="Indexes to exclude with --all")
    
    args = parser.parse_args()
    
    # Determine indexes to process
    if args.all:
        indexes = list_indexes()
        index_ids = [idx["id"] for idx in indexes if idx["id"] not in args.exclude]
        
        if not index_ids:
            logger.error("No indexes found")
            sys.exit(1)
    elif args.index_ids:
        index_ids = args.index_ids
    else:
        parser.error("Specify index IDs or use --all")
    
    # Run batch
    results = run_batch(
        index_ids=index_ids,
        dry_run=args.dry_run,
        wait=args.wait,
        stop_on_error=args.stop_on_error
    )
    
    # Exit with error if any failed
    failed = sum(1 for r in results.values() if not r["success"])
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
