# src/routes/index.py - VERSION HIÉRARCHIQUE
import os
import json
import shutil
import logging
from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, status, Header, Depends, HTTPException

from src.core.models import IndexResponse, IndexingStatus
from src.core.utils import get_index_path, get_password_hash
from src.core.indexing import index_creation_task

logger = logging.getLogger(__name__)
router = APIRouter()

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

if not INTERNAL_API_KEY:
    logger.warning("⚠️ INTERNAL_API_KEY not set! Index creation endpoint will be unsecured!")


async def verify_internal_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """Vérifie que l'appel provient bien d'Open WebUI."""
    if not INTERNAL_API_KEY:
        logger.error("INTERNAL_API_KEY not configured on server")
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: API key not set"
        )

    if x_api_key != INTERNAL_API_KEY:
        logger.warning(f"⚠️ Invalid API key attempt: {x_api_key[:10]}...")
        raise HTTPException(
            status_code=403,
            detail="Invalid API key. Only Open WebUI backend can access this endpoint."
        )

    logger.debug("✅ Valid API key - request from Open WebUI backend")
    return True


@router.get("/{index_id}/status", response_model=IndexingStatus)
async def get_indexing_status(
        index_id: str,
        _: bool = Depends(verify_internal_api_key)
):
    """
    Retourne le statut de l'indexation pour une bibliothèque donnée.
    """
    index_path = get_index_path(index_id)
    status_file = os.path.join(index_path, ".indexing_status")

    if not os.path.exists(status_file):
        return IndexingStatus(status="not_found")

    try:
        with open(status_file, "r") as f:
            status_data = json.load(f)
        return IndexingStatus(**status_data)
    except json.JSONDecodeError:
        logger.error(f"Corrupted status file for index {index_id}")
        return IndexingStatus(
            status="failed",
            error="Status file is corrupted"
        )
    except Exception as e:
        logger.error(f"Error reading status file for {index_id}: {e}")
        return IndexingStatus(
            status="failed",
            error=f"Error reading status: {str(e)}"
        )


@router.post("/{index_id}", status_code=status.HTTP_202_ACCEPTED, response_model=IndexResponse)
async def create_index(
        index_id: str,
        background_tasks: BackgroundTasks,
        files: List[UploadFile] = File(...),
        metadata_json: Optional[str] = Form(None),
        password: Optional[str] = Form(None),
        groups: Optional[str] = Form(None),
        _: bool = Depends(verify_internal_api_key)
):
    """
    Creates or updates an index asynchronously with hierarchical structure support.

    ⚠️ IMPORTANT : Les fichiers doivent être uploadés avec leur chemin relatif
    préservé dans le nom du fichier (ex: "campus/services/hash/file.pdf")
    """
    logger.info(f"📥 Creating/updating index: {index_id}")

    index_path = get_index_path(index_id)
    source_files_dir = os.path.join(index_path, "source_files")

    if os.path.exists(index_path):
        logger.info(f"Index '{index_id}' already exists. Cleaning old index data...")
        items_to_clean = ["index", ".pw_hash"]
        if groups:
            items_to_clean.append(".groups.json")

        for sub in items_to_clean:
            path_to_remove = os.path.join(index_path, sub)
            if os.path.exists(path_to_remove):
                if os.path.isdir(path_to_remove):
                    shutil.rmtree(path_to_remove)
                else:
                    os.remove(path_to_remove)
    else:
        os.makedirs(source_files_dir)

    os.makedirs(source_files_dir, exist_ok=True)

    # ✅ NOUVEAU : Sauvegarder les fichiers en préservant la hiérarchie
    files_info = []

    CRAWLER_ARTIFACTS = ["metadata.json", "page.html"]


    for file in files:
        # Le filename peut contenir le chemin relatif si uploadé depuis un scraper
        # Exemple: "campus/services/hash/guide.pdf"
        if file.filename.lower() in CRAWLER_ARTIFACTS:
            logger.info(f"  ⏭️  Skipped: {file.filename} (crawler metadata)")
            continue

        original_filename = file.filename

        # ✅ Extraire le nom de base et le chemin relatif
        if "/" in original_filename or "\\" in original_filename:
            # Normaliser les séparateurs
            relative_path = original_filename.replace("\\", "/")
            filename_only = os.path.basename(relative_path)
            relative_dir = os.path.dirname(relative_path)
        else:
            # Fichier au premier niveau
            relative_path = original_filename
            filename_only = original_filename
            relative_dir = ""

        # Créer la structure de dossiers
        target_dir = os.path.join(source_files_dir, relative_dir) if relative_dir else source_files_dir
        os.makedirs(target_dir, exist_ok=True)

        # Chemin complet de destination
        file_path = os.path.join(target_dir, filename_only)

        # Sauvegarder le fichier
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        files_info.append({
            "path": file_path,
            "filename": filename_only,
            "relative_path": relative_path  # ⬅️ CRUCIAL pour la hiérarchie
        })

        logger.info(f"  ✓ Saved: {relative_path}")

    if not files_info:
        raise HTTPException(
            status_code=400,
            detail="No valid files to index (only crawler artifacts were provided: metadata.json, page.html)"
        )

    logger.info(f"✅ {len(files_info)} file(s) saved with hierarchical structure")

    # Sauvegarder les groupes autorisés
    if groups:
        try:
            groups_data = json.loads(groups)
            if not isinstance(groups_data, list):
                raise HTTPException(
                    status_code=400,
                    detail="Groups must be a JSON array of group IDs"
                )

            groups_file = os.path.join(index_path, ".groups.json")
            with open(groups_file, "w") as f:
                json.dump({"groups": groups_data}, f)

            logger.info(f"✅ Authorized groups saved: {groups_data}")
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid JSON format for groups parameter"
            )
    else:
        logger.warning(f"⚠️ No groups specified for index {index_id}. Library will be public.")

    # Sauvegarder le mot de passe (optionnel)
    if password:
        hashed_password = get_password_hash(password)
        with open(os.path.join(index_path, ".pw_hash"), "w") as f:
            f.write(hashed_password)
        logger.info("✅ Password protection enabled")

    # Lancer l'indexation en arrière-plan
    background_tasks.add_task(index_creation_task, index_id, files_info, metadata_json)

    return {
        "status": "Accepted",
        "message": "Files saved with hierarchical structure. Indexing has started.",
        "index_path": index_path
    }