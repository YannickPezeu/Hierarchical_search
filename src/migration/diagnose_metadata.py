#!/usr/bin/env python3
"""
diagnose_metadata.py

Check what metadata is actually stored in nodes inside the docstore.
Handles LlamaIndex's __data__ wrapping and correct relationship keys.

Usage:
    python diagnose_metadata.py --index-dir ./all_indexes/large_campus2/index
    python diagnose_metadata.py --index-dir ./all_indexes/large_campus2/index --node-id 034154e8-...
"""

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter

# NodeRelationship: SOURCE="1", PREVIOUS="2", NEXT="3", PARENT="4", CHILD="5"
PARENT_REL_KEY = "4"
REL_NAMES = {"1": "SOURCE", "2": "PREVIOUS", "3": "NEXT", "4": "PARENT", "5": "CHILD"}


def sanitize_table_name(collection: str) -> str:
    return collection.replace("/", "__").replace("-", "_")


def _get_node_data(node_dict: dict) -> dict:
    """Unwrap LlamaIndex's {"__type__": ..., "__data__": {...}} format."""
    if "__data__" in node_dict:
        return node_dict["__data__"]
    return node_dict


def load_data_collection(index_dir: str) -> dict:
    sqlite_path = os.path.join(index_dir, "docstore.sqlite")
    json_path = os.path.join(index_dir, "docstore.json")
    json_bak_path = os.path.join(index_dir, "docstore.json.bak")

    if os.path.exists(sqlite_path):
        print(f"Loading from SQLite: {sqlite_path}")
        conn = sqlite3.connect(sqlite_path)
        table = sanitize_table_name("docstore/data")
        cursor = conn.execute(f"SELECT key, value FROM [{table}]")
        data = {row[0]: json.loads(row[1]) for row in cursor.fetchall()}
        conn.close()
        return data

    for path in [json_path, json_bak_path]:
        if os.path.exists(path):
            size_mb = os.path.getsize(path) / (1024*1024)
            print(f"Loading from JSON: {path} ({size_mb:.0f} MB)")
            with open(path, "r") as f:
                all_data = json.load(f)
            return all_data.get("docstore/data", {})

    print("No docstore found!")
    sys.exit(1)


def classify_node(node_id: str, node_dict: dict, all_data: dict) -> str:
    node_data = _get_node_data(node_dict)
    rels = node_data.get("relationships", {})
    parent_info = rels.get(PARENT_REL_KEY)

    if parent_info is None:
        return "PARENT"

    parent_id = parent_info.get("node_id", "")
    if parent_id not in all_data:
        return "CHILD (orphan)"

    parent_data = _get_node_data(all_data[parent_id])
    parent_rels = parent_data.get("relationships", {})
    if PARENT_REL_KEY in parent_rels:
        return "SUB-CHUNK"
    else:
        return "CHILD"


def main():
    parser = argparse.ArgumentParser(description="Diagnose metadata in docstore nodes")
    parser.add_argument("--index-dir", required=True)
    parser.add_argument("--node-id", default=None)
    parser.add_argument("--sample", type=int, default=10)
    args = parser.parse_args()

    data = load_data_collection(args.index_dir)
    print(f"Total nodes in docstore: {len(data)}\n")

    # Single node inspection
    if args.node_id:
        if args.node_id not in data:
            print(f"Node {args.node_id} not found!")
            sys.exit(1)

        node_dict = data[args.node_id]
        node_data = _get_node_data(node_dict)
        node_type = classify_node(args.node_id, node_dict, data)

        print(f"{'=' * 70}")
        print(f"NODE: {args.node_id}")
        print(f"TYPE: {node_type}")
        print(f"Wrapped in __data__: {'__data__' in node_dict}")
        print(f"{'=' * 70}")

        metadata = node_data.get("metadata", {})
        print(f"\nALL METADATA ({len(metadata)} keys):")
        for key, value in sorted(metadata.items()):
            print(f"  {key:35s} = {str(value)[:100]}")

        print(f"\nRELATIONSHIPS:")
        for rel_key, rel_val in node_data.get("relationships", {}).items():
            rel_name = REL_NAMES.get(rel_key, f"UNKNOWN({rel_key})")
            node_id_val = rel_val.get("node_id", "?") if isinstance(rel_val, dict) else "?"
            print(f"  {rel_name:10s} -> {node_id_val[:40]}")

        text = node_data.get("text", "")
        print(f"\nTEXT ({len(text)} chars, first 300):")
        print(f"  {text[:300]}")

        # Walk to parent
        parent_info = node_data.get("relationships", {}).get(PARENT_REL_KEY)
        if parent_info:
            parent_id = parent_info.get("node_id")
            if parent_id and parent_id in data:
                parent_data = _get_node_data(data[parent_id])
                parent_meta = parent_data.get("metadata", {})
                print(f"\n{'=' * 70}")
                print(f"PARENT: {parent_id}")
                print(f"{'=' * 70}")
                print(f"PARENT METADATA ({len(parent_meta)} keys):")
                for key, value in sorted(parent_meta.items()):
                    print(f"  {key:35s} = {str(value)[:100]}")
        return

    # Global analysis
    print("=" * 70)
    print("  METADATA ANALYSIS ACROSS ALL NODES")
    print("=" * 70)

    type_counts = Counter()
    all_meta_keys = Counter()
    fields_to_track = ["source_url", "source_filename", "source_relative_path", "file_name"]
    metadata_presence = {f: {"present": 0, "missing": 0, "by_type": Counter()} for f in fields_to_track}

    for node_id, node_dict in data.items():
        node_type = classify_node(node_id, node_dict, data)
        type_counts[node_type] += 1

        node_data = _get_node_data(node_dict)
        metadata = node_data.get("metadata", {})

        for key in metadata:
            all_meta_keys[key] += 1

        for field, stats in metadata_presence.items():
            if field in metadata and metadata[field]:
                stats["present"] += 1
                stats["by_type"][f"{node_type} present"] += 1
            else:
                stats["missing"] += 1
                stats["by_type"][f"{node_type} MISSING"] += 1

    print(f"\nNode types:")
    for node_type, count in type_counts.most_common():
        print(f"  {node_type:20s}: {count:>8,}")

    print(f"\nAll metadata keys found:")
    for key, count in all_meta_keys.most_common():
        pct = count / len(data) * 100
        print(f"  {key:35s}: {count:>8,} ({pct:.0f}%)")

    print(f"\nCritical field analysis:")
    for field, stats in metadata_presence.items():
        total = stats["present"] + stats["missing"]
        pct = stats["present"] / total * 100 if total > 0 else 0
        status = "OK" if pct > 90 else "PARTIAL" if pct > 0 else "MISSING"
        print(f"\n  [{status}] {field}: {stats['present']}/{total} ({pct:.1f}%)")
        for type_key, count in stats["by_type"].most_common():
            print(f"     {type_key:30s}: {count:>6,}")

    # Sample nodes missing source_url
    missing = [
        (nid, data[nid]) for nid in data
        if not _get_node_data(data[nid]).get("metadata", {}).get("source_url")
    ]

    if missing:
        print(f"\n{'=' * 70}")
        print(f"  SAMPLE NODES MISSING source_url ({len(missing)} total)")
        print(f"{'=' * 70}")

        for node_id, node_dict in missing[:args.sample]:
            node_data = _get_node_data(node_dict)
            node_type = classify_node(node_id, node_dict, data)
            meta = node_data.get("metadata", {})
            file_name = meta.get("file_name", "?")
            text = (node_data.get("text") or "")[:80]
            print(f"\n  [{node_type}] {node_id[:24]}...")
            print(f"    file_name: {file_name}")
            print(f"    meta keys: {sorted(meta.keys())}")
            print(f"    text: {text}")


if __name__ == "__main__":
    main()