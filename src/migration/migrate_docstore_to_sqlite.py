#!/usr/bin/env python3
"""
migrate_docstore_to_sqlite.py

One-time migration script that converts existing LlamaIndex docstore.json files
to SQLite-backed docstores.

ALL nodes are preserved (including sub-chunks) because LlamaIndex's vector store
retriever fetches node content from the docstore after getting IDs from FAISS.

The performance gain comes from SQLite's on-demand point lookups vs parsing
a multi-GB JSON file into RAM on startup.

Usage:
    python migrate_docstore_to_sqlite.py --dry-run                    # preview
    python migrate_docstore_to_sqlite.py                              # migrate all
    python migrate_docstore_to_sqlite.py --index-id large_campus2     # single index
    python migrate_docstore_to_sqlite.py --force                      # re-do
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

# LlamaIndex default collection names
COLLECTION_DATA = "docstore/data"
COLLECTION_REF_DOC = "docstore/ref_doc_info"
COLLECTION_METADATA = "docstore/metadata"

# NodeRelationship: SOURCE="1", PREVIOUS="2", NEXT="3", PARENT="4", CHILD="5"
PARENT_REL_KEY = "4"


def sanitize_table_name(collection: str) -> str:
    return collection.replace("/", "__").replace("-", "_")


def _get_node_data(node_dict: dict) -> dict:
    """Unwrap LlamaIndex's {"__type__": ..., "__data__": {...}} format."""
    if "__data__" in node_dict:
        return node_dict["__data__"]
    return node_dict


def count_node_types(data_collection: dict) -> dict:
    """Count node types for reporting (informational only, no filtering)."""
    counts = {"parent": 0, "child": 0, "subchunk": 0}
    all_ids = set(data_collection.keys())

    for node_id, node_dict in data_collection.items():
        node_data = _get_node_data(node_dict)
        relationships = node_data.get("relationships", {})
        parent_info = relationships.get(PARENT_REL_KEY)

        if parent_info is None:
            counts["parent"] += 1
            continue

        parent_id = parent_info.get("node_id")
        if parent_id is None or parent_id not in all_ids:
            counts["child"] += 1
            continue

        parent_data = _get_node_data(data_collection[parent_id])
        grandparent_info = parent_data.get("relationships", {}).get(PARENT_REL_KEY)

        if grandparent_info is None:
            counts["child"] += 1
        else:
            counts["subchunk"] += 1

    return counts


def migrate_single_index(index_dir: str, dry_run: bool = False, force: bool = False) -> dict:
    docstore_json_path = os.path.join(index_dir, "docstore.json")
    if not os.path.exists(docstore_json_path):
        docstore_json_path = os.path.join(index_dir, "docstore.json.bak")
    docstore_sqlite_path = os.path.join(index_dir, "docstore.sqlite")
    docstore_backup_path = os.path.join(index_dir, "docstore.json.bak")

    stats = {
        "index_dir": index_dir, "status": "skipped",
        "json_size_mb": 0, "sqlite_size_mb": 0,
        "total_nodes": 0, "parent_nodes": 0, "child_nodes": 0,
        "subchunks": 0, "ref_doc_entries": 0,
        "metadata_entries": 0, "duration_seconds": 0,
    }

    if not os.path.exists(docstore_json_path):
        logger.warning(f"  No docstore.json found in {index_dir}")
        stats["status"] = "no_json"
        return stats

    if os.path.exists(docstore_sqlite_path) and not force:
        logger.info(f"  Already migrated (docstore.sqlite exists). Use --force to redo.")
        stats["status"] = "already_migrated"
        return stats

    json_size = os.path.getsize(docstore_json_path)
    stats["json_size_mb"] = round(json_size / (1024 * 1024), 2)
    logger.info(f"  Loading docstore.json ({stats['json_size_mb']} MB)...")
    start_time = time.time()

    try:
        with open(docstore_json_path, "r", encoding="utf-8") as f:
            all_data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"  Corrupted docstore.json: {e}")
        stats["status"] = "corrupted_json"
        return stats
    except MemoryError:
        logger.error(f"  docstore.json too large for RAM ({stats['json_size_mb']} MB)")
        stats["status"] = "oom"
        return stats

    load_time = time.time() - start_time
    logger.info(f"  JSON loaded in {load_time:.1f}s")

    data_collection = all_data.get(COLLECTION_DATA, {})
    ref_doc_collection = all_data.get(COLLECTION_REF_DOC, {})
    metadata_collection = all_data.get(COLLECTION_METADATA, {})

    stats["total_nodes"] = len(data_collection)
    stats["ref_doc_entries"] = len(ref_doc_collection)
    stats["metadata_entries"] = len(metadata_collection)

    logger.info(f"  Collections: data={len(data_collection)}, "
                f"ref_doc={len(ref_doc_collection)}, metadata={len(metadata_collection)}")

    # Count node types for reporting
    logger.info(f"  Counting node types...")
    type_counts = count_node_types(data_collection)
    stats["parent_nodes"] = type_counts["parent"]
    stats["child_nodes"] = type_counts["child"]
    stats["subchunks"] = type_counts["subchunk"]

    logger.info(f"  Node breakdown:")
    logger.info(f"     Parent nodes:  {stats['parent_nodes']:>8,}")
    logger.info(f"     Child nodes:   {stats['child_nodes']:>8,}")
    logger.info(f"     Sub-chunks:    {stats['subchunks']:>8,}")
    logger.info(f"     TOTAL:         {stats['total_nodes']:>8,}  (all kept)")

    # Sanity check sample
    if data_collection:
        sample_id = next(iter(data_collection))
        sample_data = _get_node_data(data_collection[sample_id])
        logger.info(f"  Sample node: __data__ wrapped={'__data__' in data_collection[sample_id]}, "
                     f"metadata keys={sorted(sample_data.get('metadata', {}).keys())[:5]}")

    if dry_run:
        logger.info(f"  DRY RUN - would migrate {stats['total_nodes']:,} nodes to SQLite")
        stats["status"] = "dry_run"
        stats["duration_seconds"] = round(time.time() - start_time, 1)
        return stats

    # Write SQLite (ALL nodes preserved)
    logger.info(f"  Writing docstore.sqlite...")
    if os.path.exists(docstore_sqlite_path):
        os.remove(docstore_sqlite_path)

    conn = sqlite3.connect(docstore_sqlite_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    try:
        for collection_name in [COLLECTION_DATA, COLLECTION_REF_DOC, COLLECTION_METADATA]:
            table = sanitize_table_name(collection_name)
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS [{table}] "
                f"(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )

        # Insert ALL nodes
        data_table = sanitize_table_name(COLLECTION_DATA)
        logger.info(f"     Inserting {len(data_collection):,} nodes into {data_table}...")
        conn.executemany(
            f"INSERT INTO [{data_table}] (key, value) VALUES (?, ?)",
            [(k, json.dumps(v)) for k, v in data_collection.items()],
        )

        if ref_doc_collection:
            ref_table = sanitize_table_name(COLLECTION_REF_DOC)
            logger.info(f"     Inserting {len(ref_doc_collection):,} entries into {ref_table}...")
            conn.executemany(
                f"INSERT INTO [{ref_table}] (key, value) VALUES (?, ?)",
                [(k, json.dumps(v)) for k, v in ref_doc_collection.items()],
            )

        if metadata_collection:
            meta_table = sanitize_table_name(COLLECTION_METADATA)
            logger.info(f"     Inserting {len(metadata_collection):,} entries into {meta_table}...")
            conn.executemany(
                f"INSERT INTO [{meta_table}] (key, value) VALUES (?, ?)",
                [(k, json.dumps(v)) for k, v in metadata_collection.items()],
            )

        conn.commit()
        logger.info(f"  SQLite written and committed")

    except Exception as e:
        logger.error(f"  SQLite write failed: {e}")
        conn.close()
        if os.path.exists(docstore_sqlite_path):
            os.remove(docstore_sqlite_path)
        stats["status"] = "write_error"
        return stats
    finally:
        conn.close()

    sqlite_size = os.path.getsize(docstore_sqlite_path)
    stats["sqlite_size_mb"] = round(sqlite_size / (1024 * 1024), 2)

    logger.info(f"  Renaming docstore.json -> docstore.json.bak")
    os.rename(docstore_json_path, docstore_backup_path)

    stats["duration_seconds"] = round(time.time() - start_time, 1)
    stats["status"] = "success"

    logger.info(f"  Migration complete!")
    logger.info(f"     JSON:   {stats['json_size_mb']:>8} MB")
    logger.info(f"     SQLite: {stats['sqlite_size_mb']:>8} MB")
    logger.info(f"     Nodes:  {stats['total_nodes']:>8,}")
    logger.info(f"     Time:   {stats['duration_seconds']}s")

    return stats


def find_all_index_dirs(base_dir: str) -> list:
    index_dirs = []
    if not os.path.exists(base_dir):
        logger.error(f"Base directory not found: {base_dir}")
        return []
    for item in sorted(os.listdir(base_dir)):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path):
            index_subdir = os.path.join(item_path, "index")
            if os.path.isdir(index_subdir):
                index_dirs.append((item, index_subdir))
    return index_dirs


def main():
    parser = argparse.ArgumentParser(
        description="Migrate LlamaIndex docstore.json to SQLite"
    )
    parser.add_argument("--base-dir", default=os.getenv("INDEXES_BASE_DIR", "./all_indexes"))
    parser.add_argument("--index-id", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("  DOCSTORE MIGRATION: JSON -> SQLite")
    logger.info("=" * 70)
    logger.info(f"  Base dir:  {args.base_dir}")
    logger.info(f"  Dry run:   {args.dry_run}")
    logger.info(f"  Force:     {args.force}")
    logger.info("")

    if args.index_id:
        index_subdir = os.path.join(args.base_dir, args.index_id, "index")
        if not os.path.isdir(index_subdir):
            logger.error(f"Index directory not found: {index_subdir}")
            sys.exit(1)
        indexes = [(args.index_id, index_subdir)]
    else:
        indexes = find_all_index_dirs(args.base_dir)

    if not indexes:
        logger.error("No indexes found!")
        sys.exit(1)

    logger.info(f"Found {len(indexes)} index(es) to process\n")

    all_stats = []
    for index_id, index_dir in indexes:
        logger.info(f"{'─' * 60}")
        logger.info(f"Processing: {index_id}")
        logger.info(f"   Path: {index_dir}")
        stats = migrate_single_index(index_dir, dry_run=args.dry_run, force=args.force)
        stats["index_id"] = index_id
        all_stats.append(stats)
        logger.info("")

    logger.info("=" * 70)
    logger.info("  MIGRATION SUMMARY")
    logger.info("=" * 70)

    success = [s for s in all_stats if s["status"] == "success"]
    skipped = [s for s in all_stats if s["status"] in ("already_migrated", "no_json")]
    dry_runs = [s for s in all_stats if s["status"] == "dry_run"]
    errors = [s for s in all_stats if s["status"] in ("corrupted_json", "oom", "write_error")]

    total_json_mb = sum(s["json_size_mb"] for s in all_stats)
    total_sqlite_mb = sum(s["sqlite_size_mb"] for s in success)
    total_nodes = sum(s["total_nodes"] for s in all_stats)

    logger.info(f"  Migrated:   {len(success)}")
    logger.info(f"  Skipped:    {len(skipped)}")
    if dry_runs: logger.info(f"  Dry runs:   {len(dry_runs)}")
    if errors:
        logger.info(f"  Errors:     {len(errors)}")
        for s in errors:
            logger.info(f"     - {s.get('index_id', '?')}: {s['status']}")

    logger.info(f"")
    logger.info(f"  Total JSON size:       {total_json_mb:>10.1f} MB")
    logger.info(f"  Total SQLite size:     {total_sqlite_mb:>10.1f} MB")
    logger.info(f"  Total nodes:           {total_nodes:>10,}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()