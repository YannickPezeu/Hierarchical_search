# src/routes/files.py

import os
import logging
import mimetypes
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from src.core.utils import get_index_path
from src.routes.search import verify_internal_api_key, get_library_groups

logger = logging.getLogger(__name__)
router = APIRouter()

# Mapping des extensions vers les types MIME
MIME_TYPES = {
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.doc': 'application/msword',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.xls': 'application/vnd.ms-excel',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.ppt': 'application/vnd.ms-powerpoint',
    '.html': 'text/html',
    '.htm': 'text/html',
    '.json': 'application/json',
    '.md': 'text/markdown',
    '.txt': 'text/plain',
    '.csv': 'text/csv',
    '.xml': 'application/xml',
}

import glob


@router.get("/{index_id}/{filename}")
async def get_source_file(
        index_id: str,
        filename: str,
        user_groups: str = "",
        _: bool = Depends(verify_internal_api_key)
):
    """
    Serves a source file from a specific library (any format).
    Searches for the file regardless of extension.

    Args:
        index_id: The library identifier
        filename: The filename (with or without extension)
        user_groups: Comma-separated list of user's group IDs

    Returns:
        The requested file with appropriate MIME type
    """
    logger.info(f"📥 File request for: {index_id}/{filename}")

    # Vérifier les permissions de groupe
    library_groups = get_library_groups(index_id)
    if library_groups:
        user_group_list = [g.strip() for g in user_groups.split(",") if g.strip()]
        if not set(user_group_list).intersection(set(library_groups)):
            logger.warning(f"❌ Access denied for groups {user_group_list}")
            raise HTTPException(
                status_code=403,
                detail="Access denied to this library"
            )

    # Construire le chemin du dossier
    index_path = get_index_path(index_id)
    archive_dir = os.path.join(index_path, "source_files_archive")

    # ✅ Extraire le nom de base sans extension
    filename_base, _ = os.path.splitext(filename)

    # ✅ Chercher tous les fichiers qui commencent par ce nom de base
    pattern = os.path.join(archive_dir, f"{filename_base}.*")
    matching_files = glob.glob(pattern)

    # ✅ Filtrer pour éviter les faux positifs (ex: "file.pdf" ne doit pas matcher "file.backup.pdf")
    exact_matches = [
        f for f in matching_files
        if os.path.splitext(os.path.basename(f))[0] == filename_base
    ]

    if not exact_matches:
        logger.error(f"❌ No file found matching: {filename_base}.*")
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    if len(exact_matches) > 1:
        logger.warning(f"⚠️ Multiple files found for {filename_base}: {exact_matches}")
        # Prendre le premier, mais log un warning

    file_path = exact_matches[0]
    actual_filename = os.path.basename(file_path)

    logger.info(f"✅ Resolved: {filename} -> {actual_filename}")

    # Empêcher le path traversal
    if not os.path.abspath(file_path).startswith(os.path.abspath(archive_dir)):
        logger.error(f"❌ Path traversal attempt: {file_path}")
        raise HTTPException(status_code=403, detail="Invalid file path")

    # Déterminer le type MIME
    _, ext = os.path.splitext(file_path)
    media_type = MIME_TYPES.get(ext.lower())
    if not media_type:
        media_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'

    logger.info(f"📤 Serving: {file_path} (type: {media_type})")

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=actual_filename,
        headers={
            "Content-Disposition": f'inline; filename="{actual_filename}"'  # ✅ inline au lieu de attachment
        }
    )