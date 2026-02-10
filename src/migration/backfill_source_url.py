#!/usr/bin/env python3
"""
backfill_source_url.py

Patches nodes in the SQLite docstore that are missing source_url by reading
the .meta files from the md_files/ directory.

This avoids re-indexing (which took 4.5 days for the EPFL dataset).

How it works:
1. Walks md_files/ and builds a mapping: file_name.md → {source_url, source_filename, ...}
2. Scans all nodes in the SQLite docstore
3. For nodes missing source_url, looks up the mapping by file_name
4. Updates the node in-place in SQLite

Usage:
    # Dry run (report what would be fixed):
    python backfill_source_url.py --index-id large_campus2 --dry-run

    # Actually fix:
    python backfill_source_url.py --index-id large_campus2

    # Fix all indexes:
    python backfill_source_url.py
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _get_node_data(node_dict: dict) -> dict:
    """Unwrap LlamaIndex's __data__ wrapper."""
    if "__data__" in node_dict:
        return node_dict["__data__"]
    return node_dict


def build_meta_mapping(md_files_dir: str) -> dict:
    """
    Walk md_files/ and build a mapping from file_name → meta info.

    Returns:
        {"page_c32143f1.md": {"source_url": "https://...", "source_filename": "page_c32143f1.html", ...}, ...}
    """
    mapping = {}

    if not os.path.exists(md_files_dir):
        logger.error(f"md_files directory not found: {md_files_dir}")
        return mapping

    for root, dirs, files in os.walk(md_files_dir):
        for fname in files:
            if fname.endswith(".md.meta"):
                meta_path = os.path.join(root, fname)
                md_name = fname[:-5]  # remove ".meta" → "page_xxx.md"

                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)

                    if meta.get("source_url"):
                        mapping[md_name] = meta
                except Exception as e:
                    logger.warning(f"  Failed to read {meta_path}: {e}")

    logger.info(f"  Built mapping: {len(mapping)} .meta files with source_url")
    return mapping


def backfill_index(index_path: str, dry_run: bool = False) -> dict:
    """
    Backfill missing source_url in a single index's SQLite docstore.

    Args:
        index_path: Path to the index (e.g. ./all_indexes/large_campus2)
        dry_run: If True, only report what would be fixed

    Returns:
        Stats dict
    """
    index_dir = os.path.join(index_path, "index")
    md_files_dir = os.path.join(index_path, "md_files")
    sqlite_path = os.path.join(index_dir, "docstore.sqlite")

    stats = {
        "total_nodes": 0,
        "already_have_url": 0,
        "fixed": 0,
        "no_meta_available": 0,
        "no_file_name": 0,
        "unfixable_files": set(),
    }

    if not os.path.exists(sqlite_path):
        logger.error(f"  No docstore.sqlite found: {sqlite_path}")
        return stats

    if not os.path.exists(md_files_dir):
        logger.error(f"  No md_files/ directory found: {md_files_dir}")
        return stats

    # Step 1: Build file_name → meta mapping
    logger.info(f"  Scanning .meta files in: {md_files_dir}")
    meta_mapping = build_meta_mapping(md_files_dir)

    if not meta_mapping:
        logger.warning(f"  No .meta files found! Nothing to backfill.")
        return stats

    # Step 2: Scan SQLite and fix missing source_url
    logger.info(f"  Scanning SQLite docstore...")
    conn = sqlite3.connect(sqlite_path)

    # Read all nodes
    table = "docstore__data"
    cursor = conn.execute(f"SELECT key, value FROM [{table}]")

    updates = []  # (key, new_value_json) pairs to batch-update

    for row_key, row_value in cursor:
        stats["total_nodes"] += 1
        node_dict = json.loads(row_value)
        node_data = _get_node_data(node_dict)
        metadata = node_data.get("metadata", {})

        # Already has source_url? Skip
        if metadata.get("source_url"):
            stats["already_have_url"] += 1
            continue

        # Get file_name to look up meta
        file_name = metadata.get("file_name")
        if not file_name:
            stats["no_file_name"] += 1
            continue

        # Look up in meta mapping
        meta_info = meta_mapping.get(file_name)
        if not meta_info:
            stats["no_meta_available"] += 1
            stats["unfixable_files"].add(file_name)
            continue

        # Patch the metadata
        if not dry_run:
            if "source_url" in meta_info:
                metadata["source_url"] = meta_info["source_url"]
            if "source_filename" in meta_info:
                metadata["source_filename"] = meta_info["source_filename"]
            if "source_relative_path" in meta_info:
                metadata["source_relative_path"] = meta_info["source_relative_path"]

            # Write back the node_data into the wrapper
            if "__data__" in node_dict:
                node_dict["__data__"]["metadata"] = metadata
            else:
                node_dict["metadata"] = metadata

            updates.append((json.dumps(node_dict), row_key))

        stats["fixed"] += 1

    # Step 3: Batch update
    if updates and not dry_run:
        logger.info(f"  Writing {len(updates):,} updates to SQLite...")
        conn.executemany(
            f"UPDATE [{table}] SET value = ? WHERE key = ?",
            updates,
        )
        conn.commit()
        logger.info(f"  Committed.")

    conn.close()
    return stats


def find_all_index_paths(base_dir: str) -> list:
    paths = []
    if not os.path.exists(base_dir):
        return paths
    for item in sorted(os.listdir(base_dir)):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path):
            index_subdir = os.path.join(item_path, "index")
            if os.path.isdir(index_subdir):
                paths.append((item, item_path))
    return paths


def main():
    parser = argparse.ArgumentParser(
        description="Backfill missing source_url in SQLite docstore from .meta files"
    )
    parser.add_argument("--base-dir", default=os.getenv("INDEXES_BASE_DIR", "./all_indexes"))
    parser.add_argument("--index-id", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("  BACKFILL source_url FROM .meta FILES")
    logger.info("=" * 70)
    logger.info(f"  Base dir:  {args.base_dir}")
    logger.info(f"  Dry run:   {args.dry_run}")
    logger.info("")

    if args.index_id:
        index_path = os.path.join(args.base_dir, args.index_id)
        if not os.path.isdir(index_path):
            logger.error(f"Index path not found: {index_path}")
            sys.exit(1)
        indexes = [(args.index_id, index_path)]
    else:
        indexes = find_all_index_paths(args.base_dir)

    if not indexes:
        logger.error("No indexes found!")
        sys.exit(1)

    for index_id, index_path in indexes:
        logger.info(f"{'─' * 60}")
        logger.info(f"Processing: {index_id}")
        start = time.time()

        stats = backfill_index(index_path, dry_run=args.dry_run)
        elapsed = time.time() - start

        prefix = "Would fix" if args.dry_run else "Fixed"
        logger.info(f"")
        logger.info(f"  Results:")
        logger.info(f"     Total nodes:           {stats['total_nodes']:>8,}")
        logger.info(f"     Already have URL:       {stats['already_have_url']:>8,}")
        logger.info(f"     {prefix}:          {stats['fixed']:>8,}")
        logger.info(f"     No .meta available:     {stats['no_meta_available']:>8,}")
        logger.info(f"     No file_name:           {stats['no_file_name']:>8,}")
        logger.info(f"     Time:                   {elapsed:.1f}s")

        if stats["unfixable_files"]:
            unfixable = sorted(stats["unfixable_files"])
            logger.info(f"")
            logger.info(f"  Files with no .meta ({len(unfixable)}):")
            for fname in unfixable[:20]:
                logger.info(f"     - {fname}")
            if len(unfixable) > 20:
                logger.info(f"     ... and {len(unfixable) - 20} more")

        logger.info("")


if __name__ == "__main__":
    main()
