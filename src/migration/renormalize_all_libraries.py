# scripts/renormalize_all_libraries.py
import os
from src.migration.renormalize_filenames import renormalize_library

if __name__ == "__main__":
    all_indexes_dir = "./all_indexes"

    for library_id in os.listdir(all_indexes_dir):
        library_path = os.path.join(all_indexes_dir, library_id)
        if os.path.isdir(library_path):
            print(f"\n=== Processing {library_id} ===")
            renormalize_library(library_path)

    print("\nAll libraries renormalized!")