# tests/test_api.py
import os
import shutil
import time
import json
import pytest
from fastapi.testclient import TestClient

from src.main import app

# --- Constantes pour les tests ---
TEST_USER_ID = "test_user"
TEST_INDEX_ID = "test_library"
TEST_PASSWORD = "supersecret"
INDEXES_DIR = "./all_indexes"
TEST_INDEX_PATH = os.path.join(INDEXES_DIR, TEST_USER_ID, TEST_INDEX_ID)
# Chemin vers votre fichier JSON de cache (qui simule la réponse de Docling)
# Assurez-vous que ce fichier existe !
CACHED_JSON_RESPONSE_PATH = "./5.1.1_Règlement_financier.md"
SOURCE_FILES_DIR = os.path.join(INDEXES_DIR, TEST_USER_ID, TEST_INDEX_ID, 'source_files')


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module", autouse=True)
def setup_teardown_session():
    """
    Nettoie les anciens résultats de test (fichiers et dossiers) avant l'exécution.
    """
    # Liste des éléments à supprimer (dossiers et fichiers)
    items_to_remove = ["index", ".pw_hash"]

    for item_name in items_to_remove:
        path_to_remove = os.path.join(TEST_INDEX_PATH, item_name)
        if os.path.exists(path_to_remove):
            # Vérifier si c'est un dossier
            if os.path.isdir(path_to_remove):
                shutil.rmtree(path_to_remove)
            # Sinon, c'est un fichier
            else:
                os.remove(path_to_remove)

    os.makedirs(os.path.dirname(CACHED_JSON_RESPONSE_PATH), exist_ok=True)
    if not os.path.exists(CACHED_JSON_RESPONSE_PATH):
        with open(CACHED_JSON_RESPONSE_PATH, "w") as f:
            f.write('{"document":{"filename":"fake.pdf","md_content":"## Titre Mock\\n\\nContenu de test."}}')

    yield  # Les tests s'exécutent ici

#
# @pytest.mark.dependency()
# def test_create_index_with_mock_docling(client, mocker):
#     """
#     Teste la création d'un index en simulant la réponse de Docling
#     à partir d'un fichier JSON local.
#     """
#     # 1. Vérifier que votre fichier de cache JSON existe
#     assert os.path.exists(CACHED_JSON_RESPONSE_PATH), \
#         f"Le fichier de cache JSON '{CACHED_JSON_RESPONSE_PATH}' est introuvable."
#
#     # 2. Lire et parser le fichier JSON pour préparer la fausse réponse
#     with open(CACHED_JSON_RESPONSE_PATH, "r", encoding="utf-8") as f:
#         mock_response_json = json.load(f)
#
#     # 3. Intercepter `requests.post` et lui faire retourner notre contenu parsé
#     mock_post = mocker.patch("requests.post")
#     mock_post.return_value.raise_for_status.return_value = None
#     mock_post.return_value.json.return_value = mock_response_json
#
#     # 4. Envoyer une requête d'indexation
#     # Le contenu du fichier envoyé n'a pas d'importance, il sera ignoré
#     dummy_filename = "document_a_indexer.pdf"
#     metadata = {dummy_filename: "http://example.com/document.pdf"}
#
#     response = client.post(
#         f"/index/{TEST_USER_ID}/{TEST_INDEX_ID}",
#         files={'files': (dummy_filename, b"contenu factice", 'application/pdf')},
#         data={"metadata_json": json.dumps(metadata), "password": TEST_PASSWORD}
#     )
#
#     assert response.status_code == 202
#
#     print("\nIndexation (mockée) démarrée. Attente de 10 secondes...")
#     time.sleep(10)
#
#     # 5. Vérifier que l'index a été créé
#     index_dir_path = os.path.join(TEST_INDEX_PATH, "index")
#     assert os.path.exists(index_dir_path), "Le dossier 'index' n'a pas été créé. Vérifiez les logs pour une NameError."
#     assert len(os.listdir(index_dir_path)) > 0, "Le dossier 'index' est vide. Le filtre a peut-être tout supprimé."
@pytest.mark.dependency()
def test_create_index_from_existing_files(client):
    """
    Teste la création d'un index en utilisant les fichiers PDF
    placés manuellement dans le dossier source.
    """
    assert os.path.exists(SOURCE_FILES_DIR), f"Dossier source introuvable: '{SOURCE_FILES_DIR}'"
    pdf_files = [f for f in os.listdir(SOURCE_FILES_DIR) if f.endswith('.pdf')]
    assert len(pdf_files) > 0, f"Aucun PDF trouvé dans '{SOURCE_FILES_DIR}'."

    files_to_upload = []
    metadata = {}
    open_files = [] # Pour garder une trace des fichiers ouverts

    try:
        # Préparer la liste des fichiers à uploader
        for filename in pdf_files:
            file_path = os.path.join(SOURCE_FILES_DIR, filename)
            # Ouvrir le fichier et le garder dans notre liste
            file_handle = open(file_path, 'rb')
            open_files.append(file_handle)
            files_to_upload.append(('files', (filename, file_handle, 'application/pdf')))
            metadata[filename] = f"http://example.com/docs/{filename}"

        # Envoyer la requête d'indexation
        response = client.post(
            f"/index/{TEST_USER_ID}/{TEST_INDEX_ID}",
            files=files_to_upload,
            data={"metadata_json": json.dumps(metadata), "password": TEST_PASSWORD}
        )
    finally:
        # Assurer la fermeture de tous les fichiers, quoi qu'il arrive
        for f in open_files:
            f.close()

    if response.status_code != 202:
        print("Réponse de l'API (erreur):", response.json())
    assert response.status_code == 202

    print(f"\nIndexation démarrée. Attente de 20 secondes...")
    time.sleep(20)

    index_dir_path = os.path.join(TEST_INDEX_PATH, "index")
    assert os.path.exists(index_dir_path)

# Les tests de recherche restent les mêmes, mais la dépendance est mise à jour
@pytest.mark.dependency(depends=["test_create_index_from_existing_files"])
def test_search_index_success(client):
    response = client.post(
        f"/search/{TEST_USER_ID}/{TEST_INDEX_ID}",
        json={"query": "Quels sont les taux d'overhead ?", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0


@pytest.mark.dependency(depends=["test_create_index_from_existing_files"])
def test_search_wrong_password(client):
    response = client.post(
        f"/search/{TEST_USER_ID}/{TEST_INDEX_ID}",
        json={"query": "test", "password": "wrongpassword"}
    )
    assert response.status_code == 403



