# tests/test_api.py
import os
import shutil
import time
import json

import requests
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
TEST_INDEX_ID = "test_library"
TEST_PASSWORD = "supersecret"
INDEXES_DIR = "./all_indexes"
TEST_INDEX_PATH = os.path.join(INDEXES_DIR, TEST_USER_ID, TEST_INDEX_ID)
# Chemin vers votre fichier JSON de cache (qui simule la réponse de Docling)
# Assurez-vous que ce fichier existe !
CACHED_JSON_RESPONSE_PATH = "./5.1.1_Règlement_financier.md"
SOURCE_FILES_DIR = os.path.join(INDEXES_DIR, TEST_INDEX_ID, 'source_files')


QUERIES = [
    "Quels sont les taux d'overhead ?",
    "Comment sont calculés les frais de gestion ?",
    "Quelles sont les conditions de résiliation du contrat ?",
]

# Les tests de recherche restent les mêmes, mais la dépendance est mise à jour
def try_search_index_success(client):

    for query in QUERIES:
        response = client.post(
            f"/search/{TEST_USER_ID}/{TEST_INDEX_ID}",
            json={"query": query, "password": TEST_PASSWORD}
        )
        print (response.status_code )
        print(response.json())
        results = response.json()
        print (len(results) )
        print('-'*40)




def try_search_wrong_password(client):
    response = client.post(
        f"/search/{TEST_USER_ID}/{TEST_INDEX_ID}",
        json={"query": "test", "password": "wrongpassword"}
    )
    print (response.status_code )
    print(response.json())


def try_create_index_from_existing_files(client):
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
        for filename in pdf_files:
            file_path = os.path.join(SOURCE_FILES_DIR, filename)
            file_handle = open(file_path, 'rb')
            open_files.append(file_handle)
            files_to_upload.append(('files', (filename, file_handle, 'application/pdf')))
            metadata[filename] = f"http://example.com/docs/{filename}"

        # ❌ MANQUAIT : Header avec API key
        headers = {"X-API-Key": os.getenv("INTERNAL_API_KEY")}

        response = client.post(
            f"/index/LEX_FR",
            files=files_to_upload,
            data={
                "password": TEST_PASSWORD,
                "metadata_json": json.dumps(metadata),  # ❌ MANQUAIT
                "groups": json.dumps(["group-1", "group-2"])  # ❌ MANQUAIT
            },
            headers=headers  # ❌ MANQUAIT
        )
    finally:
        for f in open_files:
            f.close()

    return response

def try_search_index_success_api():
    """
    Appelle l'endpoint de recherche sur le serveur local (localhost:8000).
    """
    # L'URL de base de votre API qui tourne localement
    base_url = "http://localhost:8000"
    base_url = "http://localhost:8080"

    # On construit l'URL complète de l'endpoint
    search_url = f"{base_url}/search/LEX_FR"

    print(f"--- 📞 Appel de l'API sur {search_url} ---")

    for query in QUERIES:
        print(f"\nRecherche pour la requête : '{query}'")

        # ✅ CORRECTION 1 : L'API key va dans les HEADERS, pas dans le body
        headers = {
            "X-API-Key": os.getenv("INTERNAL_API_KEY"),
            "Content-Type": "application/json"
        }

        # ✅ CORRECTION 2 : Ajouter user_groups dans le payload
        payload = {
            "query": query,
            "user_groups": ["test-group-1", "group-2"],  # Simule les groupes de l'utilisateur
            "password": TEST_PASSWORD
        }

        try:
            # On utilise requests.post avec les headers
            response = requests.post(search_url, json=payload, headers=headers)

            # Lève une exception si le statut est une erreur (4xx ou 5xx)
            response.raise_for_status()

            # Si tout va bien, on traite la réponse
            results = response.json()
            print(f"✅ Statut de la réponse : {response.status_code}")
            print(f"📄 {len(results)} résultat(s) trouvé(s).")
            # Affiche les résultats de manière lisible
            print(json.dumps(results, indent=2, ensure_ascii=False))

        except requests.exceptions.HTTPError as e:
            print(f"❌ Erreur HTTP : {e}")
            print(f"   Statut : {response.status_code}")
            if response.text:
                print(f"   Détails : {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur lors de la requête : {e}")
            print("   Vérifiez que votre conteneur Docker est bien en cours d'exécution.")

        print('-' * 40)


if __name__ == '__main__':
    client = TestClient(app)

    # try_search_wrong_password(client)
    try_create_index_from_existing_files(client)
    try_search_index_success(client)
    # try_search_index_success_api()