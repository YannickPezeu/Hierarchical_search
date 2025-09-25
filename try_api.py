# tests/test_api.py
import os
import shutil
import time
import json
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


# Les tests de recherche restent les mêmes, mais la dépendance est mise à jour
def try_search_index_success(client):
    response = client.post(
        f"/search/{TEST_USER_ID}/{TEST_INDEX_ID}",
        json={"query": "Quels sont les taux d'overhead ?", "password": TEST_PASSWORD}
    )
    print (response.status_code )
    print(response.json())
    results = response.json()
    print (len(results) )


def try_search_wrong_password(client):
    response = client.post(
        f"/search/{TEST_USER_ID}/{TEST_INDEX_ID}",
        json={"query": "test", "password": "wrongpassword"}
    )
    print (response.status_code )
    print(response.json())

if __name__ == '__main__':
    client = TestClient(app)
    try_search_index_success(client)
    try_search_wrong_password(client)