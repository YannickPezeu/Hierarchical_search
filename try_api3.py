# tests/test_api.py - VERSION HIÉRARCHIQUE
import os
import shutil
import time
import json

import requests
from fastapi.testclient import TestClient
from llama_index.core.schema import TextNode

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
        print(response.status_code)
        print(response.json())
        results = response.json()
        print(len(results))
        print('-' * 40)


def try_search_wrong_password(client):
    response = client.post(
        f"/search/{TEST_USER_ID}/{TEST_INDEX_ID}",
        json={"query": "test", "password": "wrongpassword"}
    )
    print(response.status_code)
    print(response.json())


def try_create_index_from_existing_files(client):
    """
    Teste la création d'un index en utilisant les fichiers PDF
    placés manuellement dans le dossier source.

    ⚠️ VERSION HIÉRARCHIQUE : Les fichiers peuvent être dans des sous-dossiers
    """
    assert os.path.exists(SOURCE_FILES_DIR), f"Dossier source introuvable: '{SOURCE_FILES_DIR}'"

    # ✅ NOUVEAU : Récupération récursive des fichiers
    files_to_process = []
    for root, dirs, files in os.walk(SOURCE_FILES_DIR):
        for filename in files:
            if filename.endswith('.pdf'):
                file_path = os.path.join(root, filename)
                # Calculer le chemin relatif par rapport à SOURCE_FILES_DIR
                relative_path = os.path.relpath(file_path, SOURCE_FILES_DIR)
                files_to_process.append({
                    'path': file_path,
                    'filename': filename,
                    'relative_path': relative_path
                })

    print(f'📁 Fichiers trouvés (structure hiérarchique):')
    for f in files_to_process:
        print(f"   • {f['relative_path']}")

    assert len(files_to_process) > 0, f"Aucun PDF trouvé dans '{SOURCE_FILES_DIR}'."

    files_to_upload = []
    metadata = {}
    open_files = []

    try:
        for file_info in files_to_process:
            file_handle = open(file_info['path'], 'rb')
            open_files.append(file_handle)
            files_to_upload.append(('files', (file_info['filename'], file_handle, 'application/pdf')))
            # Utiliser le chemin relatif dans les métadonnées
            metadata[file_info['filename']] = f"http://example.com/docs/{file_info['relative_path']}"

        # Header avec API key
        headers = {"X-API-Key": os.getenv("INTERNAL_API_KEY")}

        response = client.post(
            f"/index/test_library",
            files=files_to_upload,
            data={
                "password": TEST_PASSWORD,
                "metadata_json": json.dumps(metadata),
                "groups": json.dumps(["group-1", "group-2"])
            },
            headers=headers
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


LIBRARY = 'large_campus2'


def quicktest_enrichment():
    """
    Test d'indexation avec la nouvelle structure hiérarchique.

    ⚠️ VERSION HIÉRARCHIQUE : Parcourt récursivement tous les sous-dossiers
    """
    import os
    import sys
    import glob
    import json
    sys.path.insert(0, os.path.abspath('.'))

    from src.core.indexing import index_creation_task

    # Créer un index test avec TOUS les fichiers du dossier (récursif)
    index_id = LIBRARY
    source_dir = r"all_indexes\{}\source_files".format(index_id)

    # ✅ NOUVEAU : Récupération récursive des fichiers
    print(f"📁 Analyse de la structure hiérarchique dans {source_dir}...")

    all_files = []
    for root, dirs, files in os.walk(source_dir):
        for filename in files:
            # Ignorer les fichiers cachés et temporaires
            if (filename.startswith('.')
                    or filename.endswith('.tmp')
                    or filename.endswith('.png')
                    or filename.endswith('.log')
                    or filename in ["metadata.json",
                                    "crawler.log",
                                    'failed_pages.txt',
                                    'summary.json',
                        'crawler_state.json',
                        'metadata.json'
                                    ]

            ):
                continue

            file_path = os.path.join(root, filename)
            if os.path.isfile(file_path):
                all_files.append(file_path)

    if not all_files:
        print(f"❌ Aucun fichier trouvé dans {source_dir}")
        return

    print(f"📊 {len(all_files)} fichier(s) trouvé(s) dans la hiérarchie:")

    # Grouper par dossier pour l'affichage
    files_by_dir = {}
    for file_path in all_files:
        rel_path = os.path.relpath(file_path, source_dir)
        dir_name = os.path.dirname(rel_path) if os.path.dirname(rel_path) else "(racine)"

        if dir_name not in files_by_dir:
            files_by_dir[dir_name] = []
        files_by_dir[dir_name].append(os.path.basename(file_path))

    # Afficher la structure
    for dir_name in sorted(files_by_dir.keys()):
        print(f"\n📂 {dir_name}/")
        for filename in sorted(files_by_dir[dir_name]):
            print(f"   • {filename}")

    # Simuler un upload avec chemins relatifs
    files_info = []
    metadata = {}

    for file_path in all_files:
        filename = os.path.basename(file_path)

        # ✅ CRUCIAL : Calculer le chemin relatif depuis source_dir
        relative_path = os.path.relpath(file_path, source_dir)

        files_info.append({
            "path": file_path,
            "filename": filename,
            "relative_path": relative_path  # ⬅️ NOUVEAU
        })

        # Utiliser le chemin relatif dans l'URL
        metadata[filename] = f"https://example.com/{relative_path.replace(os.sep, '/')}"

    metadata_json = json.dumps(metadata)

    print(f"\n🚀 Lancement de l'indexation hiérarchique...")
    print(f"   • Index ID: {index_id}")
    print(f"   • Fichiers: {len(files_info)}")
    print(f"   • Structure: Hiérarchique préservée")

    index_creation_task(index_id, files_info, metadata_json)

    print("\n✅ Indexation terminée. Vérifie les logs ci-dessus pour voir l'enrichissement.")
    print("📁 Structure hiérarchique préservée dans:")
    print(f"   • md_files/")
    print(f"   • source_files_archive/")


def quicktest_search_enrichment():
    """
    Test de recherche après enrichissement pour vérifier que page_number est bien présent.
    Compatible avec la structure hiérarchique.
    """
    import sys
    sys.path.insert(0, os.path.abspath('.'))

    from fastapi.testclient import TestClient
    from src.main import app

    client = TestClient(app)
    index_id = LIBRARY

    print("🔍 Test de recherche avec enrichissement des pages (structure hiérarchique)...")
    print("=" * 80)

    # Headers avec API key
    headers = {"X-API-Key": os.getenv("INTERNAL_API_KEY")}

    # Requête de recherche
    payload = {
        "query": "Quels sont les taux d'overhead ?",
        "user_groups": ["test-group-1"],  # Pas de restriction de groupe pour le test
        "password": "supersecret"  # Pas de mot de passe pour ce test
    }

    try:
        response = client.post(
            f"/search/{index_id}",
            json=payload,
            headers=headers
        )

        print(f"📊 Statut: {response.status_code}")

        if response.status_code == 200:
            results = response.json()
            print(f"📄 {len(results)} résultat(s) trouvé(s)\n")

            # Afficher les 3 premiers résultats avec détails
            for i, result in enumerate(results[:3], 1):
                print(f"\n{'─' * 80}")
                print(f"📄 Résultat #{i}")
                print(f"{'─' * 80}")
                print(f"  Title: {result.get('title', 'N/A')}")
                print(f"  Score: {result.get('score', 0):.4f}")

                # ✅ Afficher le chemin relatif si disponible
                source_relative_path = result.get('source_relative_path')
                if source_relative_path:
                    print(f"  📂 Chemin: {source_relative_path}")

                # ✨ Vérifier l'ancre
                anchor_id = result.get('node_anchor_id')
                if anchor_id:
                    print(f"  🎯 Ancre: {anchor_id}")
                    file_url = result.get('file_url', '')
                    if file_url:
                        url = f"{file_url}#{anchor_id}"
                        print(f"  🔗 URL précise: {url}")
                else:
                    print(f"  ⚠️ Pas d'ancre (fallback sur page)")

                # Aperçu du contenu
                content_preview = result.get('precise_content', '')[:200]
                print(f"\n  💬 Aperçu du contenu:")
                print(f"     {content_preview}...")

                # Hiérarchie
                hierarchy = result.get('node_hierarchy', 'N/A')
                print(f"  🌳 Hiérarchie: {hierarchy}")

            print(f"\n{'=' * 80}")
            print("✅ Test terminé avec succès!")

            # Vérification que tous les résultats ont bien page_number
            results_with_page = sum(1 for r in results if r.get('page_number') is not None)
            results_with_path = sum(1 for r in results if r.get('source_relative_path') is not None)

            print(f"\n📊 Statistiques:")
            print(f"   • Résultats avec page_number: {results_with_page}/{len(results)}")
            print(f"   • Résultats avec chemin relatif: {results_with_path}/{len(results)}")
            print(f"   • Taux d'enrichissement: {results_with_page / len(results) * 100:.1f}%")

            if results_with_page < len(results):
                print(f"\n⚠️  Attention: {len(results) - results_with_page} résultat(s) sans page_number")

            if results_with_path < len(results):
                print(f"\n⚠️  Attention: {len(results) - results_with_path} résultat(s) sans chemin relatif")
        else:
            print(f"❌ Erreur {response.status_code}")
            print(f"Détails: {response.text}")

    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        import traceback
        traceback.print_exc()


# def test_hierarchical_structure():
#     """
#     Test spécifique pour vérifier que la structure hiérarchique est correctement préservée.
#     """
#     import sys
#     sys.path.insert(0, os.path.abspath('.'))
#
#     index_id = LIBRARY
#     index_path = os.path.join(INDEXES_DIR, index_id)
#
#     print("🔍 Vérification de la structure hiérarchique...")
#     print("=" * 80)
#
#     # Vérifier md_files/
#     md_files_dir = os.path.join(index_path, "md_files")
#     if os.path.exists(md_files_dir):
#         print(f"\n📂 Structure de md_files/:")
#         for root, dirs, files in os.walk(md_files_dir):
#             level = root.replace(md_files_dir, '').count(os.sep)
#             indent = '  ' * level
#             folder_name = os.path.basename(root)
#             print(f'{indent}📁 {folder_name}/')
#
#             sub_indent = '  ' * (level + 1)
#             for file in files:
#                 if not file.startswith('.'):
#                     print(f'{sub_indent}📄 {file}')
#
#     # Vérifier source_files_archive/
#     archive_dir = os.path.join(index_path, "source_files_archive")
#     if os.path.exists(archive_dir):
#         print(f"\n📂 Structure de source_files_archive/:")
#         for root, dirs, files in os.walk(archive_dir):
#             level = root.replace(archive_dir, '').count(os.sep)
#             indent = '  ' * level
#             folder_name = os.path.basename(root)
#             print(f'{indent}📁 {folder_name}/')
#
#             sub_indent = '  ' * (level + 1)
#             for file in files:
#                 if not file.startswith('.'):
#                     print(f'{sub_indent}📄 {file}')
#
#     print(f"\n{'=' * 80}")
#     print("✅ Vérification de la structure terminée!")

import os
import json
import requests
from requests.auth import HTTPBasicAuth
from fastapi.testclient import TestClient
from dotenv import load_dotenv

# Charger les variables d'environnement (.env)
load_dotenv()


def get_all_active_kb_ids():
    """
    Interroge ServiceNow pour récupérer les IDs de TOUTES les Knowledge Bases actives.
    """
    sn_username = "WS_AI"
    sn_password = os.getenv("SERVICENOW_KEY")
    base_url = "https://epfl.service-now.com/api/now/table/kb_knowledge_base"

    print("🔍 Récupération de la liste des Knowledge Bases actives depuis ServiceNow...")

    params = {
        "sysparm_query": "active=true",  # Uniquement les actives
        "sysparm_fields": "sys_id,title",  # On ne veut que l'ID et le titre
        "sysparm_limit": 100
    }

    try:
        response = requests.get(
            base_url,
            params=params,
            auth=HTTPBasicAuth(sn_username, sn_password),
            headers={"Accept": "application/json"}
        )

        if response.status_code == 200:
            kbs = response.json().get('result', [])
            print(f"✅ {len(kbs)} Knowledge Bases trouvées.")

            # Affichage pour info
            for kb in kbs:
                print(f"   - {kb['title']} ({kb['sys_id']})")

            # Retourne la liste des IDs
            return [kb['sys_id'] for kb in kbs]
        else:
            print(f"❌ Erreur ServiceNow: {response.status_code} - {response.text}")
            return []

    except Exception as e:
        print(f"❌ Exception lors de la récupération des KBs: {e}")
        return []


def try_trigger_servicenow_ingestion_all(client):
    """
    Récupère toutes les KBs et déclenche l'ingestion massive.
    """
    print("\n🚀 Lancement de l'ingestion COMPLETE de ServiceNow...")
    print("=" * 60)

    # 1. Récupération dynamique des IDs
    all_kb_ids = get_all_active_kb_ids()

    if not all_kb_ids:
        print("⚠️ Aucune KB trouvée ou erreur de connexion. Abandon.")
        return

    # 2. Configuration du payload
    test_index_id = "servicenow_full_index"
    # Optionnel : définir des groupes si nécessaire, sinon None (public/admin)
    test_groups = ["public"]

    payload = {
        "index_id": test_index_id,
        "kb_ids": all_kb_ids,
        "user_groups": test_groups
    }

    # 3. Headers (API Key du backend)
    api_key = os.getenv("INTERNAL_API_KEY")
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    print(f"\n📤 Envoi de la requête d'ingestion au Backend RAG...")
    print(f"   Index cible : {test_index_id}")
    print(f"   Nombre de KBs : {len(all_kb_ids)}")

    try:
        # 4. Appel de l'API Backend
        response = client.post(
            "/servicenow/ingest",
            json=payload,
            headers=headers
        )

        print(f"\n📊 Statut API Backend: {response.status_code}")

        if response.status_code in [200, 202]:
            print("✅ Démarrage réussi !")
            print(json.dumps(response.json(), indent=2))
            print("\n⏳ L'ingestion tourne en arrière-plan. Cela va prendre du temps.")
        else:
            print(f"❌ Échec de l'appel API: {response.text}")

    except Exception as e:
        print(f"❌ Erreur technique: {e}")


# --- Bloc d'exécution ---
if __name__ == '__main__':
    from src.main import app

    client = TestClient(app)

    # Lancer l'ingestion massive
    try_trigger_servicenow_ingestion_all(client)