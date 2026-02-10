#!/usr/bin/env python3
"""
run_indexing.py - CLI tool for creating/updating search indexes

This script calls the same API endpoints as Open WebUI, ensuring consistency.

Usage:
    # Re-index from source_files/ (calls POST /index/{index_id})
    python -m scripts.run_indexing LEX_FR

    # List all available indexes
    python -m scripts.run_indexing --list

    # Show status of an index
    python -m scripts.run_indexing LEX_FR --status

    # Wait for indexing to complete
    python -m scripts.run_indexing LEX_FR --wait

    # Dry run (show what would be done)
    python -m scripts.run_indexing LEX_FR --dry-run

Environment:
    Requires .env file with:
    - INTERNAL_API_KEY: API key for authentication
    - API_BASE_URL: Base URL of the API (default: http://localhost:8079)
"""

import os
import sys
import json
import time
import logging
import argparse
import requests
from pathlib import Path
from typing import Optional, List

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables
from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from src.core.config import ALL_INDEXES_DIR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8079")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

# Supported file extensions
SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.html', '.htm', '.pptx', '.xlsx'}
EXCLUDED_FILES = {'metadata.json', 'page.html'}


def get_api_headers() -> dict:
    """Get headers for API requests."""
    if not INTERNAL_API_KEY:
        logger.error("INTERNAL_API_KEY not set in environment!")
        sys.exit(1)
    return {"X-API-Key": INTERNAL_API_KEY}


def list_indexes() -> List[dict]:
    """List all available indexes with their status."""
    indexes = []

    if not os.path.exists(ALL_INDEXES_DIR):
        logger.warning(f"Indexes directory not found: {ALL_INDEXES_DIR}")
        return indexes

    for item in os.listdir(ALL_INDEXES_DIR):
        item_path = os.path.join(ALL_INDEXES_DIR, item)
        if os.path.isdir(item_path):
            index_info = {
                "id": item,
                "path": item_path,
                "has_index": os.path.exists(os.path.join(item_path, "index")),
                "has_source_files": os.path.exists(os.path.join(item_path, "source_files")),
            }

            # Count source files
            source_dir = os.path.join(item_path, "source_files")
            if os.path.exists(source_dir):
                count = sum(
                    1 for f in Path(source_dir).rglob("*")
                    if f.is_file()
                    and f.suffix.lower() in SUPPORTED_EXTENSIONS
                    and f.name.lower() not in EXCLUDED_FILES
                )
                index_info["source_file_count"] = count
            else:
                index_info["source_file_count"] = 0

            # Get status from API
            try:
                resp = requests.get(
                    f"{API_BASE_URL}/index/{item}/status",
                    headers=get_api_headers(),
                    timeout=5
                )
                if resp.status_code == 200:
                    index_info["status"] = resp.json().get("status", "unknown")
                else:
                    index_info["status"] = "api_error"
            except requests.exceptions.ConnectionError:
                index_info["status"] = "api_offline"
            except Exception as e:
                index_info["status"] = f"error: {e}"

            indexes.append(index_info)

    return indexes


def get_index_status(index_id: str) -> dict:
    """Get detailed status of an index via API."""
    try:
        resp = requests.get(
            f"{API_BASE_URL}/index/{index_id}/status",
            headers=get_api_headers(),
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {"status": "error", "error": "API server not reachable"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def collect_source_files(index_id: str) -> List[dict]:
    """
    Collect all source files for an index.

    Returns list of dicts with path, filename, relative_path
    """
    source_dir = os.path.join(ALL_INDEXES_DIR, index_id, "source_files")

    if not os.path.exists(source_dir):
        logger.error(f"Source files directory not found: {source_dir}")
        return []

    files = []
    for file_path in Path(source_dir).rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if file_path.name.lower() in EXCLUDED_FILES:
            continue

        relative_path = str(file_path.relative_to(source_dir))
        files.append({
            'path': str(file_path),
            'filename': file_path.name,
            'relative_path': relative_path
        })

    return files


def create_index(
        index_id: str,
        groups: Optional[List[str]] = None,
        password: Optional[str] = None,
        dry_run: bool = False
) -> bool:
    """
    Create/update an index by calling the API endpoint.

    This mimics exactly what the test does - collect files and POST to /index/{index_id}
    """
    # Collect files
    files_to_process = collect_source_files(index_id)

    if not files_to_process:
        logger.error(f"No source files found for index: {index_id}")
        return False

    logger.info(f"📁 Found {len(files_to_process)} files to index:")
    for f in files_to_process[:10]:
        logger.info(f"   • {f['relative_path']}")
    if len(files_to_process) > 10:
        logger.info(f"   ... and {len(files_to_process) - 10} more")

    if dry_run:
        logger.info("\n" + "=" * 60)
        logger.info("DRY RUN - Would call API:")
        logger.info(f"  POST {API_BASE_URL}/index/{index_id}")
        logger.info(f"  Files: {len(files_to_process)}")
        logger.info(f"  Groups: {groups}")
        logger.info("=" * 60)
        return True

    # Build multipart form data (same as the test)
    files_to_upload = []
    metadata = {}
    open_files = []

    try:
        for file_info in files_to_process:
            file_handle = open(file_info['path'], 'rb')
            open_files.append(file_handle)

            # Determine MIME type
            ext = Path(file_info['path']).suffix.lower()
            mime_types = {
                '.pdf': 'application/pdf',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.html': 'text/html',
                '.htm': 'text/html',
                '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            }
            mime_type = mime_types.get(ext, 'application/octet-stream')

            # Use relative_path as filename to preserve hierarchy
            files_to_upload.append(
                ('files', (file_info['relative_path'], file_handle, mime_type))
            )

            # Metadata placeholder (could be enhanced to read from metadata.json)
            metadata[file_info['filename']] = f"file://{file_info['relative_path']}"

        # Build form data
        data = {
            "metadata_json": json.dumps(metadata)
        }

        if password:
            data["password"] = password

        if groups:
            data["groups"] = json.dumps(groups)

        # Call API
        logger.info(f"\n🚀 Calling API: POST {API_BASE_URL}/index/{index_id}")

        response = requests.post(
            f"{API_BASE_URL}/index/{index_id}",
            files=files_to_upload,
            data=data,
            headers=get_api_headers(),
            timeout=300  # 5 minutes for large uploads
        )

        if response.status_code == 202:
            logger.info("✅ Index creation started (HTTP 202 Accepted)")
            logger.info(f"   Response: {response.json()}")
            return True
        else:
            logger.error(f"❌ API error: {response.status_code}")
            logger.error(f"   Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Cannot connect to API at {API_BASE_URL}")
        logger.error("   Is the server running? Start it with: python -m src.main")
        return False
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return False
    finally:
        for f in open_files:
            f.close()


def wait_for_completion(index_id: str, timeout: int = 3600, poll_interval: int = 10) -> bool:
    """
    Wait for indexing to complete.

    Args:
        index_id: Index identifier
        timeout: Maximum wait time in seconds (default: 1 hour)
        poll_interval: Polling interval in seconds

    Returns:
        True if completed successfully, False otherwise
    """
    logger.info(f"⏳ Waiting for indexing to complete (timeout: {timeout}s)...")

    start_time = time.time()

    while time.time() - start_time < timeout:
        status = get_index_status(index_id)
        current_status = status.get("status", "unknown")

        if current_status == "completed":
            duration = status.get("duration_seconds", "unknown")
            num_docs = status.get("num_documents", "unknown")
            logger.info(f"✅ Indexing completed!")
            logger.info(f"   Duration: {duration}s")
            logger.info(f"   Documents: {num_docs}")
            return True

        elif current_status == "failed":
            error = status.get("error", "Unknown error")
            logger.error(f"❌ Indexing failed: {error}")
            return False

        elif current_status == "in_progress":
            elapsed = int(time.time() - start_time)
            logger.info(f"   ... still in progress ({elapsed}s elapsed)")

        else:
            logger.warning(f"   Unknown status: {current_status}")

        time.sleep(poll_interval)

    logger.error(f"❌ Timeout waiting for indexing ({timeout}s)")
    return False


def main():
    parser = argparse.ArgumentParser(
        description="CLI tool for managing search indexes (calls API)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all indexes
  python -m scripts.run_indexing --list

  # Show status of an index
  python -m scripts.run_indexing LEX_FR --status

  # Create/update an index
  python -m scripts.run_indexing LEX_FR

  # Create index and wait for completion
  python -m scripts.run_indexing LEX_FR --wait

  # Dry run
  python -m scripts.run_indexing LEX_FR --dry-run

Note: The API server must be running (python -m src.main)
"""
    )

    parser.add_argument(
        "index_id",
        nargs="?",
        help="Index identifier (e.g., LEX_FR, large_campus)"
    )

    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all available indexes"
    )

    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Show detailed status of the index"
    )

    parser.add_argument(
        "--wait", "-w",
        action="store_true",
        help="Wait for indexing to complete"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it"
    )

    parser.add_argument(
        "--groups", "-g",
        nargs="+",
        help="Authorized groups for the index"
    )

    parser.add_argument(
        "--password", "-p",
        help="Password protection for the index"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="Timeout for --wait in seconds (default: 3600)"
    )

    args = parser.parse_args()

    # Handle --list
    if args.list:
        indexes = list_indexes()
        if not indexes:
            print("No indexes found.")
            return

        print("\n" + "=" * 70)
        print("AVAILABLE INDEXES")
        print("=" * 70)

        for idx in indexes:
            status_icon = {
                "completed": "✅",
                "in_progress": "⏳",
                "failed": "❌",
                "api_offline": "🔌",
            }.get(idx["status"], "❓")

            print(f"\n{status_icon} {idx['id']}")
            print(f"   Status: {idx['status']}")
            print(f"   Source files: {idx.get('source_file_count', 'N/A')}")
            print(f"   Has index: {idx['has_index']}")

        print("\n" + "=" * 70)
        return

    # Require index_id for other operations
    if not args.index_id:
        parser.error("index_id is required (or use --list)")

    # Handle --status
    if args.status:
        status = get_index_status(args.index_id)
        print("\n" + "=" * 60)
        print(f"INDEX STATUS: {args.index_id}")
        print("=" * 60)
        print(json.dumps(status, indent=2, default=str))
        print("=" * 60)
        return

    # Create/update index
    logger.info("=" * 60)
    logger.info(f"INDEXING: {args.index_id}")
    logger.info("=" * 60)

    success = create_index(
        index_id=args.index_id,
        groups=args.groups,
        password=args.password,
        dry_run=args.dry_run
    )

    if not success:
        sys.exit(1)

    # Wait for completion if requested
    if args.wait and not args.dry_run:
        success = wait_for_completion(args.index_id, timeout=args.timeout)
        sys.exit(0 if success else 1)

    sys.exit(0)


if __name__ == "__main__":
    main()