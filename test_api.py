# tests/test_api.py
import os
import shutil
import time
import json
import pytest
from fastapi.testclient import TestClient

from src.main import app

# --- Constantes pour les tests ---
TEST_INDEX_ID = "test_library"
TEST_PASSWORD = "supersecret"
TEST_API_KEY = os.getenv("INTERNAL_API_KEY", "test-api-key-for-local-testing")
TEST_USER_GROUPS = ["test-group-1", "test-group-2"]

INDEXES_DIR = "./all_indexes"
TEST_INDEX_PATH = os.path.join(INDEXES_DIR, TEST_INDEX_ID)
SOURCE_FILES_DIR = os.path.join(TEST_INDEX_PATH, 'source_files')


@pytest.fixture(scope="module")
def client():
    """Client de test FastAPI"""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def api_key_header():
    """Header avec uniquement l'API key (sans Content-Type)"""
    return {"X-API-Key": TEST_API_KEY}


@pytest.fixture(scope="module")
def api_headers_json():
    """Headers avec l'API key pour les requêtes JSON"""
    return {
        "X-API-Key": TEST_API_KEY,
        "Content-Type": "application/json"
    }


@pytest.fixture(scope="module", autouse=True)
def setup_teardown_session():
    """
    Nettoie les anciens résultats de test avant l'exécution.
    """
    # Liste des éléments à supprimer
    items_to_remove = ["index", ".pw_hash", ".groups.json", "md_files"]

    for item_name in items_to_remove:
        path_to_remove = os.path.join(TEST_INDEX_PATH, item_name)
        if os.path.exists(path_to_remove):
            if os.path.isdir(path_to_remove):
                shutil.rmtree(path_to_remove)
            else:
                os.remove(path_to_remove)

    print(f"\n✅ Nettoyage effectué pour {TEST_INDEX_PATH}")

    yield  # Les tests s'exécutent ici


@pytest.mark.dependency()
def test_create_index_from_existing_files(client, api_key_header):
    """
    Teste la création d'un index en utilisant les fichiers PDF
    placés manuellement dans le dossier source.
    """
    assert os.path.exists(SOURCE_FILES_DIR), f"Dossier source introuvable: '{SOURCE_FILES_DIR}'"
    pdf_files = [f for f in os.listdir(SOURCE_FILES_DIR) if f.endswith('.pdf')]
    assert len(pdf_files) > 0, f"Aucun PDF trouvé dans '{SOURCE_FILES_DIR}'."

    files_to_upload = []
    metadata = {}
    open_files = []

    try:
        # Préparer la liste des fichiers à uploader
        for filename in pdf_files:
            file_path = os.path.join(SOURCE_FILES_DIR, filename)
            file_handle = open(file_path, 'rb')
            open_files.append(file_handle)
            files_to_upload.append(('files', (filename, file_handle, 'application/pdf')))
            metadata[filename] = f"http://example.com/docs/{filename}"

        # Envoyer la requête avec l'API key et les groupes
        # IMPORTANT: Ne pas mettre Content-Type dans les headers quand on envoie des fichiers
        response = client.post(
            f"/index/{TEST_INDEX_ID}",
            files=files_to_upload,
            data={
                "metadata_json": json.dumps(metadata),
                "password": TEST_PASSWORD,
                "groups": json.dumps(TEST_USER_GROUPS)
            },
            headers=api_key_header  # Uniquement l'API key, pas de Content-Type
        )
    finally:
        for f in open_files:
            f.close()

    if response.status_code != 202:
        print("Réponse de l'API (erreur):", response.json())
    assert response.status_code == 202

    print(f"\n✅ Indexation démarrée. Attente de 20 secondes...")
    time.sleep(20)

    index_dir_path = os.path.join(TEST_INDEX_PATH, "index")
    assert os.path.exists(index_dir_path), "Le dossier 'index' n'a pas été créé"

    # Vérifier que le fichier .groups.json existe
    groups_file = os.path.join(TEST_INDEX_PATH, ".groups.json")
    assert os.path.exists(groups_file), "Le fichier .groups.json n'a pas été créé"

    # Vérifier le contenu du fichier .groups.json
    with open(groups_file, "r") as f:
        groups_data = json.load(f)
        assert groups_data.get("groups") == TEST_USER_GROUPS
        print(f"✅ Groupes autorisés vérifiés: {groups_data['groups']}")


@pytest.mark.dependency(depends=["test_create_index_from_existing_files"])
def test_search_index_success(client, api_headers_json):
    """Test de recherche avec les bons groupes"""
    response = client.post(
        f"/search/{TEST_INDEX_ID}",
        json={
            "query": "Quels sont les taux d'overhead ?",
            "user_groups": TEST_USER_GROUPS,
            "password": TEST_PASSWORD
        },
        headers=api_headers_json
    )

    if response.status_code != 200:
        print("Erreur:", response.json())

    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0
    print(f"\n✅ {len(results)} résultats trouvés")


@pytest.mark.dependency(depends=["test_create_index_from_existing_files"])
def test_search_wrong_password(client, api_headers_json):
    """Test avec un mauvais mot de passe"""
    response = client.post(
        f"/search/{TEST_INDEX_ID}",
        json={
            "query": "test",
            "user_groups": TEST_USER_GROUPS,
            "password": "wrongpassword"
        },
        headers=api_headers_json
    )
    assert response.status_code == 403
    print("\n✅ Mot de passe incorrect refusé")


@pytest.mark.dependency(depends=["test_create_index_from_existing_files"])
def test_search_wrong_groups(client, api_headers_json):
    """Test avec des groupes non autorisés"""
    response = client.post(
        f"/search/{TEST_INDEX_ID}",
        json={
            "query": "test",
            "user_groups": ["wrong-group", "another-wrong-group"],
            "password": TEST_PASSWORD
        },
        headers=api_headers_json
    )
    assert response.status_code == 403
    error_detail = response.json()
    assert "Access denied" in error_detail.get("detail", "")
    print(f"\n✅ Accès refusé comme attendu: {error_detail['detail']}")


@pytest.mark.dependency(depends=["test_create_index_from_existing_files"])
def test_search_without_api_key(client):
    """Test sans API key (devrait échouer)"""
    response = client.post(
        f"/search/{TEST_INDEX_ID}",
        json={
            "query": "test",
            "user_groups": TEST_USER_GROUPS,
            "password": TEST_PASSWORD
        }
    )
    assert response.status_code == 422  # FastAPI retourne 422 si header manquant
    print(f"\n✅ Requête sans API key refusée: {response.status_code}")


@pytest.mark.dependency(depends=["test_create_index_from_existing_files"])
def test_search_with_wrong_api_key(client):
    """Test avec une mauvaise API key"""
    response = client.post(
        f"/search/{TEST_INDEX_ID}",
        json={
            "query": "test",
            "user_groups": TEST_USER_GROUPS,
            "password": TEST_PASSWORD
        },
        headers={
            "X-API-Key": "wrong-api-key",
            "Content-Type": "application/json"
        }
    )
    assert response.status_code == 403
    print("\n✅ Requête avec mauvaise API key refusée")


@pytest.mark.dependency(depends=["test_create_index_from_existing_files"])
def test_search_multiple_queries(client, api_headers_json):
    """Test avec plusieurs requêtes différentes"""
    queries = [
        "Quels sont les taux d'overhead ?",
        "règlement financier",
        "budget"
    ]

    for query in queries:
        response = client.post(
            f"/search/{TEST_INDEX_ID}",
            json={
                "query": query,
                "user_groups": TEST_USER_GROUPS,
                "password": TEST_PASSWORD
            },
            headers=api_headers_json
        )

        assert response.status_code == 200
        results = response.json()
        print(f"\n🔍 Query: '{query}' -> {len(results)} résultats")

        # Afficher les 2 premiers résultats
        for i, result in enumerate(results[:2], 1):
            print(f"  {i}. {result.get('title', 'Sans titre')} (score: {result.get('score', 0):.3f})")


@pytest.mark.dependency(depends=["test_create_index_from_existing_files"])
def test_search_with_one_matching_group(client, api_headers_json):
    """Test avec un seul groupe correspondant (devrait réussir)"""
    response = client.post(
        f"/search/{TEST_INDEX_ID}",
        json={
            "query": "test",
            "user_groups": ["test-group-1", "some-other-group"],  # Un seul groupe match
            "password": TEST_PASSWORD
        },
        headers=api_headers_json
    )
    assert response.status_code == 200
    print("\n✅ Accès autorisé avec un seul groupe correspondant")


@pytest.mark.dependency(depends=["test_create_index_from_existing_files"])
def test_search_no_password_when_required(client, api_headers_json):
    """Test sans mot de passe quand il est requis"""
    response = client.post(
        f"/search/{TEST_INDEX_ID}",
        json={
            "query": "test",
            "user_groups": TEST_USER_GROUPS
            # Pas de password
        },
        headers=api_headers_json
    )
    assert response.status_code == 401
    print("\n✅ Mot de passe manquant détecté")