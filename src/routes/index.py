# src/routes/index.py
import os
import shutil
import logging
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, status

from src.core.models import IndexResponse
from src.core.utils import get_index_path, get_password_hash
from src.core.indexing import index_creation_task

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/{user_id}/{index_id}", status_code=status.HTTP_202_ACCEPTED, response_model=IndexResponse)
async def create_index(
        user_id: str,
        index_id: str,
        background_tasks: BackgroundTasks,
        files: List[UploadFile] = File(...),
        metadata_json: Optional[str] = Form(None),
        password: Optional[str] = Form(None)
):
    """
    Creates or updates an index asynchronously.
    If the index exists, its data is cleaned before re-indexing.
    """
    index_path = get_index_path(user_id, index_id)
    source_files_dir = os.path.join(index_path, "source_files")

    if os.path.exists(index_path):
        logger.info(f"Index '{index_id}' already exists. Cleaning old index data...")
        for sub in ["index", ".pw_hash"]:
            path_to_remove = os.path.join(index_path, sub)
            if os.path.exists(path_to_remove):
                if os.path.isdir(path_to_remove):
                    shutil.rmtree(path_to_remove)
                else:
                    os.remove(path_to_remove)
    else:
        os.makedirs(source_files_dir)

    os.makedirs(source_files_dir, exist_ok=True)

    files_info = []
    for file in files:
        file_path = os.path.join(source_files_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        files_info.append({"path": file_path, "filename": file.filename})

    if password:
        hashed_password = get_password_hash(password)
        with open(os.path.join(index_path, ".pw_hash"), "w") as f:
            f.write(hashed_password)

    background_tasks.add_task(index_creation_task, user_id, index_id, files_info, metadata_json)

    return {"status": "Accepted", "message": "Files saved. Indexing has started.", "index_path": index_path}