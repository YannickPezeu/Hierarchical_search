# src/routes/index.py
import os
import json
import shutil
import logging
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, status, Header, Depends, HTTPException

from src.core.models import IndexResponse
from src.core.utils import get_index_path, get_password_hash
from src.core.indexing import index_creation_task

logger = logging.getLogger(__name__)
router = APIRouter()

# ✅ Récupérer l'API key depuis l'environnement
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

if not INTERNAL_API_KEY:
    logger.warning("⚠️ INTERNAL_API_KEY not set! Index creation endpoint will be unsecured!")


# ✅ Dépendance pour vérifier l'API key
async def verify_internal_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """
    Vérifie que l'appel provient bien d'Open WebUI.
    """
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


# À ajouter dans src/routes/index.py après l'endpoint create_index

from src.core.models import IndexResponse, IndexingStatus


@router.get("/{index_id}/status", response_model=IndexingStatus)
async def get_indexing_status(
        index_id: str,
        _: bool = Depends(verify_internal_api_key)
):
    """
    Retourne le statut de l'indexation pour une bibliothèque donnée.

    Statuts possibles :
    - "not_found": L'indexation n'a jamais été démarrée
    - "in_progress": L'indexation est en cours
    - "completed": L'indexation s'est terminée avec succès
    - "failed": L'indexation a échoué

    Args:
        index_id: L'identifiant de la bibliothèque/index

    Returns:
        IndexingStatus avec les détails du statut
    """
    index_path = get_index_path(index_id)
    status_file = os.path.join(index_path, ".indexing_status")

    # Si le fichier de statut n'existe pas
    if not os.path.exists(status_file):
        return IndexingStatus(status="not_found")

    # Lire et retourner le statut
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
        groups: Optional[str] = Form(None),  # ✅ NOUVEAU : JSON string des group IDs
        _: bool = Depends(verify_internal_api_key)  # ✅ Vérifie l'API key
):
    """
    Creates or updates an index asynchronously with group-based permissions.

    This endpoint should ONLY be called by Open WebUI backend.

    Args:
        index_id: The library/index identifier
        files: List of files to index
        metadata_json: Optional JSON string with file metadata (URLs, etc.)
        password: Optional password for additional protection
        groups: Optional JSON string with list of authorized group IDs

    Returns:
        Status and index path information
    """
    logger.info(f"📥 Creating/updating index: {index_id}")

    index_path = get_index_path(index_id)
    source_files_dir = os.path.join(index_path, "source_files")

    if os.path.exists(index_path):
        logger.info(f"Index '{index_id}' already exists. Cleaning old index data...")
        # Nettoyage mais on garde .groups.json si pas de nouveaux groupes fournis
        items_to_clean = ["index", ".pw_hash"]
        if groups:  # Si de nouveaux groupes sont fournis, on nettoie aussi l'ancien fichier
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

    # Sauvegarder les fichiers
    files_info = []
    for file in files:
        file_path = os.path.join(source_files_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        files_info.append({"path": file_path, "filename": file.filename})

    logger.info(f"✅ {len(files_info)} file(s) saved")

    # ✅ Sauvegarder les groupes autorisés
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
        "message": "Files saved. Indexing has started.",
        "index_path": index_path
    }