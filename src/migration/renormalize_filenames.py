# scripts/renormalize_filenames.py
import os
import shutil
from pathlib import Path
from src.components import normalize_filename


def renormalize_library(library_path: str):
    """
    Renormalise tous les fichiers d'une library existante.
    """
    source_files_dir = os.path.join(library_path, "source_files")
    archive_dir = os.path.join(library_path, "source_files_archive")
    md_files_dir = os.path.join(library_path, "md_files")

    # Créer le dossier archive s'il n'existe pas
    os.makedirs(archive_dir, exist_ok=True)

    # Traiter source_files
    if os.path.exists(source_files_dir):
        for filename in os.listdir(source_files_dir):
            old_path = os.path.join(source_files_dir, filename)
            if not os.path.isfile(old_path):
                continue

            normalized = normalize_filename(filename)
            new_path = os.path.join(source_files_dir, normalized)

            if old_path != new_path:
                print(f"Renaming: {filename} -> {normalized}")
                shutil.move(old_path, new_path)

            # Copier vers archive
            archive_path = os.path.join(archive_dir, normalized)
            shutil.copy2(new_path, archive_path)

    # Traiter md_files
    if os.path.exists(md_files_dir):
        for filename in os.listdir(md_files_dir):
            old_path = os.path.join(md_files_dir, filename)
            if not os.path.isfile(old_path):
                continue

            normalized = normalize_filename(filename)
            new_path = os.path.join(md_files_dir, normalized)

            if old_path != new_path:
                print(f"Renaming MD: {filename} -> {normalized}")
                shutil.move(old_path, new_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python scripts/renormalize_filenames.py <library_id>")
        sys.exit(1)

    library_id = sys.argv[1]
    library_path = f"./all_indexes/{library_id}"

    if not os.path.exists(library_path):
        print(f"Error: Library {library_id} not found at {library_path}")
        sys.exit(1)

    print(f"Renormalizing library: {library_id}")
    renormalize_library(library_path)
    print("Done!")