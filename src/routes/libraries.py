# src/routes/libraries.py
import os
import json
import logging
from typing import List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from src.core.utils import get_index_path
from src.routes.search import verify_internal_api_key

logger = logging.getLogger(__name__)
router = APIRouter()


class LibraryInfo(BaseModel):
    """Information sur une bibliothèque disponible"""
    library_id: str
    library_name: str
    is_public: bool
    authorized_groups: List[str]


class LibrariesResponse(BaseModel):
    """Réponse contenant la liste des bibliothèques disponibles"""
    libraries: List[LibraryInfo]
    total_count: int


def get_all_library_ids() -> List[str]:
    """
    Récupère tous les IDs de bibliothèques depuis le dossier all_indexes.

    Returns:
        Liste des IDs de bibliothèques (noms de dossiers)
    """
    indexes_base_dir = os.getenv("INDEXES_BASE_DIR", "./all_indexes")

    if not os.path.exists(indexes_base_dir):
        logger.warning(f"Indexes directory not found: {indexes_base_dir}")
        return []

    library_ids = []
    for item in os.listdir(indexes_base_dir):
        item_path = os.path.join(indexes_base_dir, item)
        if os.path.isdir(item_path):
            library_ids.append(item)

    logger.info(f"Found {len(library_ids)} libraries in {indexes_base_dir}")
    return library_ids


def get_library_groups_info(library_id: str) -> tuple[List[str], bool]:
    """
    Lit les groupes autorisés depuis le fichier .groups.json.

    Args:
        library_id: ID de la bibliothèque

    Returns:
        Tuple (liste des groupes, is_public)
        - Si le fichier n'existe pas : ([], True) - bibliothèque publique par défaut
        - Si "public" est dans les groupes : (groupes, True)
        - Sinon : (groupes, False)
    """
    index_path = get_index_path(library_id)
    groups_file = os.path.join(index_path, ".groups.json")

    if not os.path.exists(groups_file):
        logger.info(f"No .groups.json for library {library_id}. Treating as public (legacy).")
        return [], True

    try:
        with open(groups_file, "r") as f:
            data = json.load(f)
            groups = data.get("groups", [])

            # Vérifier si "public" est dans les groupes
            is_public = "public" in [g.lower() for g in groups]

            logger.debug(f"Library {library_id} groups: {groups}, is_public: {is_public}")
            return groups, is_public

    except Exception as e:
        logger.error(f"Failed to read groups file for {library_id}: {e}")
        return [], True  # En cas d'erreur, traiter comme public par sécurité


def user_has_access(user_groups: List[str], library_groups: List[str], is_public: bool) -> bool:
    """
    Vérifie si l'utilisateur a accès à la bibliothèque.

    Args:
        user_groups: Groupes de l'utilisateur
        library_groups: Groupes autorisés de la bibliothèque
        is_public: Si la bibliothèque est publique

    Returns:
        True si l'utilisateur a accès, False sinon
    """
    # Si la bibliothèque est publique, tout le monde y a accès
    if is_public:
        return True

    # Si pas de groupes définis, bibliothèque publique par défaut
    if not library_groups:
        return True

    # Vérifier l'intersection entre les groupes de l'utilisateur et ceux de la bibliothèque
    user_group_set = set(g.lower() for g in user_groups)
    library_group_set = set(g.lower() for g in library_groups)

    has_access = bool(user_group_set.intersection(library_group_set))
    return has_access


@router.get("/", response_model=LibrariesResponse)
async def list_available_libraries(
        user_groups: str = Query(..., description="Comma-separated list of user's group IDs"),
        _: bool = Depends(verify_internal_api_key)
):
    """
    Liste toutes les bibliothèques disponibles pour l'utilisateur.

    Logique d'accès :
    - Si .groups.json n'existe pas : bibliothèque publique (legacy)
    - Si .groups.json contient "public" : bibliothèque accessible à tous
    - Sinon : vérifier si l'utilisateur appartient à un des groupes autorisés

    Args:
        user_groups: Liste des groupes de l'utilisateur (séparés par des virgules)

    Returns:
        Liste des bibliothèques accessibles avec leurs informations
    """
    logger.info(f"📚 Listing libraries for user groups: {user_groups}")

    # Parser les groupes de l'utilisateur
    user_group_list = [g.strip() for g in user_groups.split(",") if g.strip()]
    logger.info(f"   Parsed user groups: {user_group_list}")

    # Récupérer toutes les bibliothèques
    all_library_ids = get_all_library_ids()

    if not all_library_ids:
        logger.warning("No libraries found")
        return LibrariesResponse(libraries=[], total_count=0)

    # Filtrer les bibliothèques accessibles
    accessible_libraries = []

    for library_id in all_library_ids:
        try:
            library_groups, is_public = get_library_groups_info(library_id)

            # Vérifier l'accès
            if user_has_access(user_group_list, library_groups, is_public):
                library_info = LibraryInfo(
                    library_id=library_id,
                    library_name=library_id.replace("_", " ").title(),  # Formater le nom
                    is_public=is_public,
                    authorized_groups=library_groups
                )
                accessible_libraries.append(library_info)
                logger.info(f"   ✅ Access granted to: {library_id}")
            else:
                logger.info(f"   ❌ Access denied to: {library_id}")

        except Exception as e:
            logger.error(f"Error processing library {library_id}: {e}")
            continue

    logger.info(f"✅ Found {len(accessible_libraries)} accessible libraries out of {len(all_library_ids)}")

    return LibrariesResponse(
        libraries=accessible_libraries,
        total_count=len(accessible_libraries)
    )