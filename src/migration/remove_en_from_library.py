#!/usr/bin/env python3
"""
Script to recursively remove all 'en' and 'de' folders from a directory tree.
Target directory: ../../all_indexes/large_campus
"""

import os
import shutil
import sys
from pathlib import Path


def find_folders_to_remove(base_path, folder_names):
    """
    Find all folders with specified names in the directory tree.

    Args:
        base_path: Path object for the base directory
        folder_names: Set of folder names to find

    Returns:
        List of Path objects for folders to be removed
    """
    folders_to_remove = []

    # Walk through directory tree
    for root, dirs, files in os.walk(base_path):
        # Check each directory
        for dir_name in dirs[:]:  # Use slice to avoid modifying list while iterating
            if dir_name in folder_names:
                folder_path = Path(root) / dir_name
                folders_to_remove.append(folder_path)
                # Remove from dirs list to avoid walking into it
                dirs.remove(dir_name)

    return folders_to_remove


def remove_folders(folders_list):
    """
    Remove all folders in the list.

    Args:
        folders_list: List of Path objects to remove

    Returns:
        Tuple of (successful_count, failed_list)
    """
    successful = 0
    failed = []

    for folder in folders_list:
        try:
            shutil.rmtree(folder)
            print(f"✓ Removed: {folder}")
            successful += 1
        except Exception as e:
            print(f"✗ Failed to remove {folder}: {e}")
            failed.append((folder, str(e)))

    return successful, failed


def main():
    # Define target directory (relative to script location)
    script_dir = Path(__file__).parent
    target_dir = script_dir / ".." / ".." / "all_indexes" / "large_campus"
    target_dir = target_dir.resolve()  # Get absolute path

    # Folders to remove
    folders_to_remove_names = {"en", "de"}

    print("=" * 60)
    print("FOLDER REMOVAL SCRIPT")
    print("=" * 60)
    print(f"Target directory: {target_dir}")
    print(f"Folders to remove: {', '.join(folders_to_remove_names)}")
    print("=" * 60)

    # Check if target directory exists
    if not target_dir.exists():
        print(f"ERROR: Target directory does not exist: {target_dir}")
        sys.exit(1)

    if not target_dir.is_dir():
        print(f"ERROR: Target path is not a directory: {target_dir}")
        sys.exit(1)

    # Find all folders to remove
    print("\nSearching for folders to remove...")
    folders_list = find_folders_to_remove(target_dir, folders_to_remove_names)

    if not folders_list:
        print("No matching folders found. Nothing to remove.")
        sys.exit(0)

    # Display folders to be removed
    print(f"\nFound {len(folders_list)} folder(s) to remove:")
    for folder in folders_list:
        # Show relative path for readability
        try:
            rel_path = folder.relative_to(target_dir)
            print(f"  - {rel_path}")
        except ValueError:
            print(f"  - {folder}")

    # Confirmation prompt
    print("\n" + "!" * 60)
    print("WARNING: This operation will permanently delete these folders")
    print("and ALL their contents (including subfolders and files)!")
    print("!" * 60)

    confirmation = input("\nDo you want to proceed? Type 'YES' to confirm: ")

    if confirmation != "YES":
        print("Operation cancelled.")
        sys.exit(0)

    # Remove folders
    print("\nRemoving folders...")
    successful, failed = remove_folders(folders_list)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Successfully removed: {successful} folder(s)")
    print(f"Failed to remove: {len(failed)} folder(s)")

    if failed:
        print("\nFailed removals:")
        for folder, error in failed:
            print(f"  - {folder}: {error}")

    print("\nOperation completed.")


if __name__ == "__main__":
    main()