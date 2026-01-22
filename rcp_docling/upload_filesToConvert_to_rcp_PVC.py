#!/usr/bin/env python3
"""
upload_with_progress.py - Upload vers RCP avec logs de progression

Usage:
    python upload_with_progress.py <local_dir> [remote_dir]
"""

import os
import sys
import subprocess
import time
from pathlib import Path

NAMESPACE = "runai-sci-ic-mr-pezeu"
POD_NAME = "file-transfer-pod"
DEPTH = 2  # Niveau de profondeur pour découper les uploads


def get_size(path: Path) -> int:
    """Taille d'un fichier ou dossier."""
    if path.is_file():
        return path.stat().st_size
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total


def format_size(bytes_size: int) -> str:
    if bytes_size > 1024 * 1024 * 1024:
        return f"{bytes_size / 1024 / 1024 / 1024:.2f} GB"
    return f"{bytes_size / 1024 / 1024:.1f} MB"


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}min"
    else:
        return f"{seconds / 3600:.1f}h"


def get_items_at_depth(base_dir: Path, depth: int) -> list:
    """
    Récupère tous les dossiers/fichiers à une profondeur donnée.
    depth=1: sous-dossiers directs (about/, campus/, ...)
    depth=2: sous-sous-dossiers (about/xxx/, about/yyy/, campus/zzz/, ...)
    """
    items = []

    def recurse(current: Path, current_depth: int):
        if current_depth == depth:
            items.append(current)
            return

        if current.is_dir():
            for child in current.iterdir():
                if child.is_dir():
                    recurse(child, current_depth + 1)
                elif current_depth == depth - 1:
                    # Fichiers au niveau juste avant la profondeur cible
                    items.append(child)

    for child in base_dir.iterdir():
        recurse(child, 1)

    return items


def kubectl_cp(local_path: str, remote_path: str, cwd: str) -> tuple[bool, str]:
    """Execute kubectl cp depuis un répertoire donné."""
    cmd = ["kubectl", "cp", local_path, f"{POD_NAME}:{remote_path}", "-n", NAMESPACE]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.returncode == 0, result.stderr


def main():
    if len(sys.argv) < 2:
        print("Usage: python upload_with_progress.py <local_dir> [remote_dir]")
        sys.exit(1)

    local_dir = Path(sys.argv[1]).resolve()
    remote_dir = sys.argv[2] if len(sys.argv) > 2 else "/scratch/docling/input"

    if not local_dir.exists():
        print(f"❌ Directory not found: {local_dir}")
        sys.exit(1)

    # Récupérer les items à uploader (niveau 2)
    print(f"\n📊 Scanning {local_dir} at depth {DEPTH}...")
    items = get_items_at_depth(local_dir, DEPTH)

    if not items:
        # Fallback: niveau 1
        print("   No items at depth 2, trying depth 1...")
        items = list(local_dir.iterdir())

    # Calculer les tailles
    print(f"   Calculating sizes for {len(items)} items...")
    item_sizes = {}
    total_size = 0
    for item in items:
        size = get_size(item)
        item_sizes[item] = size
        total_size += size

    print(f"\n📦 Total: {format_size(total_size)} in {len(items)} item(s)")
    print(f"📤 Destination: {POD_NAME}:{remote_dir}")
    print("-" * 60)

    # Créer le dossier distant racine
    subprocess.run([
        "kubectl", "exec", POD_NAME, "-n", NAMESPACE, "--",
        "mkdir", "-p", remote_dir
    ], capture_output=True)

    # Upload item par item
    uploaded_size = 0
    uploaded_count = 0
    failed_count = 0
    start_time = time.time()

    for i, item in enumerate(items, 1):
        item_size = item_sizes[item]

        # Chemin relatif depuis local_dir
        rel_path = item.relative_to(local_dir)
        remote_path = f"{remote_dir}/{rel_path.as_posix()}"

        # Calculer ETA
        elapsed = time.time() - start_time
        if uploaded_size > 0 and elapsed > 0:
            speed = uploaded_size / elapsed
            remaining = total_size - uploaded_size
            eta = remaining / speed if speed > 0 else 0
            eta_str = f"ETA: {format_duration(eta)}"
            speed_str = f"{format_size(speed)}/s"
        else:
            eta_str = "ETA: ..."
            speed_str = "..."

        # Progress bar
        pct = (uploaded_size / total_size * 100) if total_size > 0 else 0
        bar_w = 25
        filled = int(bar_w * pct / 100)
        bar = "█" * filled + "░" * (bar_w - filled)

        # Status line
        status = f"[{bar}] {pct:5.1f}% | {i}/{len(items)} | {format_size(uploaded_size)}/{format_size(total_size)} | {speed_str} | {eta_str}"
        print(f"\r{status}", end="", flush=True)

        # Créer le dossier parent distant
        parent_remote = f"{remote_dir}/{rel_path.parent.as_posix()}" if rel_path.parent != Path('.') else remote_dir
        subprocess.run([
            "kubectl", "exec", POD_NAME, "-n", NAMESPACE, "--",
            "mkdir", "-p", parent_remote
        ], capture_output=True)

        # Upload avec chemin relatif
        success, err = kubectl_cp(str(rel_path), remote_path, cwd=str(local_dir))

        if success:
            uploaded_size += item_size
            uploaded_count += 1
        else:
            failed_count += 1
            print(f"\n   ⚠️ Failed: {rel_path} - {err.strip()[:50]}")

    # Final
    elapsed = time.time() - start_time
    print(f"\r[{'█' * bar_w}] 100.0% | Done!{' ' * 50}")
    print("-" * 60)
    print(f"\n✅ Uploaded: {uploaded_count}/{len(items)} items")
    if failed_count:
        print(f"❌ Failed: {failed_count}")
    print(f"📦 Size: {format_size(uploaded_size)}")
    print(f"⏱️  Time: {format_duration(elapsed)}")
    if elapsed > 0:
        print(f"🚀 Speed: {format_size(uploaded_size / elapsed)}/s")


if __name__ == "__main__":
    main()