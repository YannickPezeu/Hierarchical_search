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
print("SOURCE_FILES_DIR", os.path.abspath(SOURCE_FILES_DIR))


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


import time
import json
import os

import time


def wait_for_indexing_completion(
        client,
        index_id: str,
        api_headers: dict,
        timeout: int = 120,
        poll_interval: int = 2
) -> dict:
    """
    Attend que l'indexation soit terminée en interrogeant l'API de statut.

    Args:
        client: TestClient FastAPI
        index_id: Identifiant de l'index
        api_headers: Headers avec l'API key
        timeout: Temps maximum d'attente en secondes (défaut: 120s)
        poll_interval: Intervalle entre chaque vérification en secondes (défaut: 2s)

    Returns:
        dict: Statut final de l'indexation

    Raises:
        TimeoutError: Si l'indexation n'est pas terminée dans le temps imparti
        Exception: Si l'indexation a échoué
    """
    start_time = time.time()

    print(f"\n⏳ Attente de la fin de l'indexation (timeout: {timeout}s)...")

    while True:
        elapsed = time.time() - start_time

        # Vérifier le timeout
        if elapsed > timeout:
            raise TimeoutError(
                f"L'indexation n'est pas terminée après {timeout}s. "
                f"Augmentez le timeout ou vérifiez les logs."
            )

        # Interroger l'API de statut
        response = client.get(
            f"/index/{index_id}/status",
            headers=api_headers
        )

        if response.status_code != 200:
            print(f"  [⚠️] Erreur lors de la vérification du statut: {response.status_code}")
            time.sleep(poll_interval)
            continue

        status_data = response.json()
        status = status_data.get("status")

        if status == "completed":
            duration = status_data.get("duration_seconds", 0)
            num_docs = status_data.get("num_documents", "?")
            print(f"  ✅ Indexation terminée en {duration:.1f}s ({num_docs} documents)")
            return status_data

        elif status == "failed":
            error = status_data.get("error", "Unknown error")
            error_type = status_data.get("error_type", "")
            raise Exception(f"L'indexation a échoué ({error_type}): {error}")

        elif status == "in_progress":
            print(f"  [{elapsed:.1f}s] Indexation en cours...")
            time.sleep(poll_interval)

        elif status == "not_found":
            print(f"  [{elapsed:.1f}s] Attente du démarrage de l'indexation...")
            time.sleep(poll_interval)

        else:
            print(f"  [⚠️] Statut inconnu: {status}")
            time.sleep(poll_interval)


@pytest.mark.dependency()
def test_create_index_from_existing_files(client, api_key_header):
    """
    Teste la création d'un index en utilisant les fichiers PDF
    placés manuellement dans le dossier source.
    """
    assert os.path.exists(SOURCE_FILES_DIR), f"Dossier source introuvable: '{SOURCE_FILES_DIR}'"
    print(f"\n📁 Dossier des fichiers source : '{SOURCE_FILES_DIR}'")
    pdf_files = [f for f in os.listdir(SOURCE_FILES_DIR) if f.endswith('.pdf')]
    print(f"📄 Fichiers PDF trouvés : {pdf_files}")
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

        print('files_to_upload:', [f[1][0] for f in files_to_upload])

        # Envoyer la requête avec l'API key et les groupes
        response = client.post(
            f"/index/{TEST_INDEX_ID}",
            files=files_to_upload,
            data={
                "metadata_json": json.dumps(metadata),
                "password": TEST_PASSWORD,
                "groups": json.dumps(TEST_USER_GROUPS)
            },
            headers=api_key_header
        )
    finally:
        for f in open_files:
            f.close()

    if response.status_code != 202:
        print("Réponse de l'API (erreur):", response.json())
    assert response.status_code == 202

    # ✅ NOUVEAU : Attendre intelligemment la fin de l'indexation via l'API
    try:
        status_data = wait_for_indexing_completion(
            client=client,
            index_id=TEST_INDEX_ID,
            api_headers=api_key_header,
            timeout=120,  # 2 minutes max
            poll_interval=2  # Vérifier toutes les 2 secondes
        )
        print(f"📊 Statut final: {status_data}")
    except TimeoutError as e:
        pytest.fail(str(e))
    except Exception as e:
        pytest.fail(f"Indexation échouée: {e}")

    # Vérifications
    index_dir_path = os.path.join(TEST_INDEX_PATH, "index")
    assert os.path.exists(index_dir_path), "Le dossier 'index' n'a pas été créé"

    # Vérifier qu'il y a des nodes dans le docstore
    docstore_file = os.path.join(index_dir_path, "docstore.json")
    assert os.path.exists(docstore_file), "Le fichier docstore.json n'existe pas"

    with open(docstore_file, 'r') as f:
        docstore_data = json.load(f)
        num_nodes = len(docstore_data.get("docstore/data", {}))
        print(f"📦 Nodes dans le docstore: {num_nodes}")
        assert num_nodes > 0, "Aucun node n'a été créé dans l'index"

    # Vérifier que le fichier .groups.json existe
    groups_file = os.path.join(TEST_INDEX_PATH, ".groups.json")
    assert os.path.exists(groups_file), "Le fichier .groups.json n'a pas été créé"

    # Vérifier le contenu du fichier .groups.json
    with open(groups_file, "r") as f:
        groups_data = json.load(f)
        assert groups_data.get("groups") == TEST_USER_GROUPS
        print(f"✅ Groupes autorisés vérifiés: {groups_data['groups']}")


@pytest.mark.dependency(depends=["test_create_index_from_existing_files"])
def test_get_indexing_status(client, api_key_header):
    """Test de l'endpoint de statut après indexation réussie"""
    response = client.get(
        f"/index/{TEST_INDEX_ID}/status",
        headers=api_key_header
    )

    assert response.status_code == 200
    status_data = response.json()

    assert status_data["status"] == "completed"
    assert status_data["num_documents"] > 0
    assert status_data["duration_seconds"] > 0

    print(f"\n✅ Statut récupéré avec succès:")
    print(f"   - Statut: {status_data['status']}")
    print(f"   - Documents: {status_data['num_documents']}")
    print(f"   - Durée: {status_data['duration_seconds']:.1f}s")


@pytest.mark.dependency()
def test_get_status_nonexistent_index(client, api_key_header):
    """Test de l'endpoint de statut pour un index qui n'existe pas"""
    response = client.get(
        f"/index/nonexistent_library/status",
        headers=api_key_header
    )

    assert response.status_code == 200
    status_data = response.json()
    assert status_data["status"] == "not_found"

    print(f"\n✅ Statut 'not_found' retourné correctement pour un index inexistant")



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