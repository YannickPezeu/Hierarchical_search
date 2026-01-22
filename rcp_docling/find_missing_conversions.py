#!/usr/bin/env python3
"""
find_missing_conversions.py - Identifie les fichiers source sans .md correspondant

Usage:
    python find_missing_conversions.py <index_path>
"""

import os
import sys
import shutil
from pathlib import Path
from collections import defaultdict

# Extensions à convertir
SOURCE_EXTENSIONS = {'.html', '.htm', '.pdf', '.docx', '.pptx', '.xlsx'}

# Fichiers à ignorer (artifacts du crawler)
IGNORE_FILES = {'metadata.json', 'page.html'}


def find_missing_conversions(index_path: Path):
    source_dir = index_path / "source_files"
    md_dir = index_path / "md_files"
    output_dir = index_path / "to_convert"

    if not source_dir.exists():
        print(f"❌ source_files/ not found in {index_path}")
        sys.exit(1)

    if not md_dir.exists():
        print(f"⚠️  md_files/ not found - all files will be marked for conversion")
        md_dir.mkdir(exist_ok=True)

    # Nettoyer le dossier de sortie
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir()

    # Stats
    stats = defaultdict(int)
    missing_files = []

    print(f"\n🔍 Scanning {source_dir}...")
    print("-" * 50)

    # Parcourir tous les fichiers source
    scanned = 0
    for source_file in source_dir.rglob("*"):
        if not source_file.is_file():
            continue

        scanned += 1

        # Log de progression toutes les 100 fichiers
        if scanned % 100 == 0:
            print(f"   Scanned: {scanned} | Converted: {stats['already_converted']} | Missing: {stats['missing']}")

        # Ignorer les fichiers système
        if source_file.name.lower() in IGNORE_FILES:
            stats['ignored'] += 1
            continue

        # Vérifier l'extension
        ext = source_file.suffix.lower()
        if ext not in SOURCE_EXTENSIONS:
            stats['unsupported'] += 1
            continue

        stats['total'] += 1
        stats[f'ext_{ext}'] += 1

        # Calculer le chemin relatif et le .md correspondant
        relative_path = source_file.relative_to(source_dir)
        expected_md = md_dir / relative_path.with_suffix('.md')

        # Vérifier si le .md existe
        if expected_md.exists():
            stats['already_converted'] += 1
        else:
            stats['missing'] += 1
            missing_files.append((source_file, relative_path))

            # Copier vers to_convert/
            dest_file = output_dir / relative_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, dest_file)

    # Log final
    print(f"   Scanned: {scanned} | Converted: {stats['already_converted']} | Missing: {stats['missing']}")
    print("-" * 50)

    # Résumé
    print(f"\n✅ {stats['already_converted']} already converted")
    print(f"❌ {stats['missing']} to convert")

    if missing_files:
        total_size = sum(f.stat().st_size for f, _ in missing_files)
        print(f"📦 {total_size / 1024 / 1024:.1f} MB to upload → {output_dir}")

    return missing_files


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python find_missing_conversions.py <index_path>")
        sys.exit(1)

    index_path = Path(sys.argv[1])
    if not index_path.exists():
        print(f"❌ Path not found: {index_path}")
        sys.exit(1)

    find_missing_conversions(index_path)