# src/routes/files.py - VERSION HIÉRARCHIQUE

import os
import logging
import mimetypes
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from src.core.utils import get_index_path
from src.routes.search import verify_internal_api_key, get_library_groups

logger = logging.getLogger(__name__)
router = APIRouter()

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


def find_file_in_hierarchy(base_dir: str, filename_base: str) -> str:
    """
    Cherche un fichier dans toute l'arborescence d'un dossier.

    Args:
        base_dir: Dossier racine où chercher (ex: source_files_archive/)
        filename_base: Nom de base du fichier sans extension (ex: "guide")

    Returns:
        Chemin complet vers le fichier trouvé, ou None
    """
    import glob

    # Chercher récursivement tous les fichiers qui matchent
    pattern = os.path.join(base_dir, "**", f"{filename_base}.*")
    matching_files = glob.glob(pattern, recursive=True)

    # Filtrer pour ne garder que les correspondances exactes
    exact_matches = [
        f for f in matching_files
        if os.path.splitext(os.path.basename(f))[0] == filename_base
    ]

    return exact_matches[0] if exact_matches else None


CRAWLER_ARTIFACTS = ["metadata.json", "page.html"]


@router.get("/{index_id}/{filename:path}")
async def get_source_file(
        index_id: str,
        filename: str,
        user_groups: str = "",
        _: bool = Depends(verify_internal_api_key)
):
    """
    Serves a source file from a specific library with hierarchical structure support.

    ⚠️ NOUVEAU : Le filename peut contenir un chemin relatif
    Exemples:
    - /files/my_lib/guide.pdf
    - /files/my_lib/campus/services/guide.pdf

    Args:
        index_id: The library identifier
        filename: The filename with optional relative path
        user_groups: Comma-separated list of user's group IDs

    Returns:
        The requested file with appropriate MIME type
    """
    logger.info(f"📥 File request for: {index_id}/{filename}")

    # ✅ NOUVEAU : Bloquer les artifacts du crawler
    filename_base = os.path.basename(filename).lower()
    if filename_base in CRAWLER_ARTIFACTS:
        logger.warning(f"❌ Blocked request for crawler artifact: {filename_base}")
        raise HTTPException(
            status_code=403,
            detail=f"Crawler artifacts ({filename_base}) cannot be served"
        )

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

    # ✅ NOUVEAU : Gérer les chemins avec hiérarchie
    # Normaliser les séparateurs
    filename_normalized = filename.replace("\\", "/")

    # Extraire le nom de base sans extension
    filename_base = os.path.splitext(os.path.basename(filename_normalized))[0]

    # Stratégie 1 : Chemin direct (si le chemin relatif complet est fourni)
    direct_path = os.path.join(archive_dir, filename_normalized)

    # Chercher toutes les extensions possibles pour ce chemin direct
    direct_dir = os.path.dirname(direct_path)
    if os.path.exists(direct_dir):
        import glob
        pattern = os.path.join(direct_dir, f"{filename_base}.*")
        direct_matches = glob.glob(pattern)

        exact_direct_matches = [
            f for f in direct_matches
            if os.path.splitext(os.path.basename(f))[0] == filename_base
        ]

        if exact_direct_matches:
            file_path = exact_direct_matches[0]
            logger.info(f"✅ Found via direct path: {os.path.relpath(file_path, archive_dir)}")
        else:
            # Stratégie 2 : Recherche dans toute l'arborescence
            logger.info(f"🔍 Not found at direct path, searching hierarchy...")
            file_path = find_file_in_hierarchy(archive_dir, filename_base)

            if not file_path:
                logger.error(f"❌ No file found matching: {filename_base}")
                raise HTTPException(status_code=404, detail=f"File not found: {filename}")

            logger.info(f"✅ Found via hierarchy search: {os.path.relpath(file_path, archive_dir)}")
    else:
        # Le dossier direct n'existe pas, chercher dans toute l'arborescence
        logger.info(f"🔍 Direct directory doesn't exist, searching hierarchy...")
        file_path = find_file_in_hierarchy(archive_dir, filename_base)

        if not file_path:
            logger.error(f"❌ No file found matching: {filename_base}")
            raise HTTPException(status_code=404, detail=f"File not found: {filename}")

        logger.info(f"✅ Found via hierarchy search: {os.path.relpath(file_path, archive_dir)}")

    actual_filename = os.path.basename(file_path)

    # Empêcher le path traversal
    if not os.path.abspath(file_path).startswith(os.path.abspath(archive_dir)):
        logger.error(f"❌ Path traversal attempt: {file_path}")
        raise HTTPException(status_code=403, detail="Invalid file path")

    # Déterminer le type MIME
    _, ext = os.path.splitext(file_path)
    media_type = MIME_TYPES.get(ext.lower())
    if not media_type:
        media_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'

    logger.info(f"📤 Serving: {os.path.relpath(file_path, archive_dir)} (type: {media_type})")

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=actual_filename,
        headers={
            "Content-Disposition": f'inline; filename="{actual_filename}"'
        }
    )