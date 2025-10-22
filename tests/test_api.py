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
    print('Source Files dir:', os.path.realpath(SOURCE_FILES_DIR))
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


@pytest.mark.dependency()
def test_corrupted_and_valid_pdf_handling(client, api_key_header):
    """
    Teste que :
    1. Les PDFs corrompus sont détectés, supprimés et ne sont pas indexés
    2. Les PDFs valides passent la validation et sont indexés correctement
    """
    # Setup : chemins des fichiers de test
    test_data_dir = "tests/data"
    corrupted_pdf_source = os.path.join(test_data_dir, "corruptedPDF.pdf")
    valid_pdf_source = os.path.join(test_data_dir, "validPDF.pdf")

    # Vérifier que les fichiers de test existent
    assert os.path.exists(corrupted_pdf_source), f"Fichier de test manquant: {corrupted_pdf_source}"
    assert os.path.exists(valid_pdf_source), f"Fichier de test manquant: {valid_pdf_source}"

    print(f"\n📋 Test de validation PDF")
    print(f"   - PDF corrompu : {corrupted_pdf_source}")
    print(f"   - PDF valide : {valid_pdf_source}")

    # Créer un index temporaire pour ce test
    test_index_id = "test_pdf_validation"
    test_index_path = os.path.join(INDEXES_DIR, test_index_id)

    # Nettoyer si existe déjà
    if os.path.exists(test_index_path):
        shutil.rmtree(test_index_path)
        print(f"   - Nettoyage de l'index précédent")

    # Préparer l'upload (on copie pour ne pas perdre les originaux)
    files_to_upload = []
    metadata = {}
    open_files = []

    try:
        # Copier et ouvrir le PDF corrompu
        with open(corrupted_pdf_source, 'rb') as src:
            corrupted_content = src.read()

        # Créer un fichier temporaire pour le PDF corrompu
        import tempfile
        corrupted_temp = tempfile.NamedTemporaryFile(delete=False, suffix='_corruptedPDF_copy.pdf')
        corrupted_temp.write(corrupted_content)
        corrupted_temp.close()

        # Copier et ouvrir le PDF valide
        with open(valid_pdf_source, 'rb') as src:
            valid_content = src.read()

        valid_temp = tempfile.NamedTemporaryFile(delete=False, suffix='_validPDF_copy.pdf')
        valid_temp.write(valid_content)
        valid_temp.close()

        # Préparer les fichiers pour l'upload
        corrupted_handle = open(corrupted_temp.name, 'rb')
        valid_handle = open(valid_temp.name, 'rb')
        open_files.extend([corrupted_handle, valid_handle])

        files_to_upload.append(('files', ('corruptedPDF_copy.pdf', corrupted_handle, 'application/pdf')))
        files_to_upload.append(('files', ('validPDF_copy.pdf', valid_handle, 'application/pdf')))

        metadata['corruptedPDF_copy.pdf'] = "http://example.com/test/corrupted.pdf"
        metadata['validPDF_copy.pdf'] = "http://example.com/test/valid.pdf"

        print(f"📤 Envoi de 2 fichiers (1 corrompu + 1 valide)...")

        # Envoyer la requête
        response = client.post(
            f"/index/{test_index_id}",
            files=files_to_upload,
            data={
                "metadata_json": json.dumps(metadata),
                "groups": json.dumps(["test-pdf-group"])
            },
            headers=api_key_header
        )
    finally:
        # Fermer les fichiers
        for f in open_files:
            f.close()
        # Supprimer les fichiers temporaires
        try:
            os.unlink(corrupted_temp.name)
            os.unlink(valid_temp.name)
        except:
            pass

    assert response.status_code == 202, f"Indexation non acceptée: {response.json()}"
    print(f"   ✅ Requête d'indexation acceptée (202)")

    # Attendre la fin de l'indexation
    try:
        status_data = wait_for_indexing_completion(
            client=client,
            index_id=test_index_id,
            api_headers=api_key_header,
            timeout=120,
            poll_interval=2
        )
    except Exception as e:
        # Afficher les logs si disponibles
        if os.path.exists(test_index_path):
            status_file = os.path.join(test_index_path, ".indexing_status")
            if os.path.exists(status_file):
                with open(status_file, 'r') as f:
                    print(f"\n⚠️ Statut d'indexation: {f.read()}")
        pytest.fail(f"Erreur lors de l'indexation: {e}")

    # VÉRIFICATIONS
    print(f"\n🔍 Vérification des résultats...")

    # 1. Vérifier que le PDF corrompu n'est PAS dans l'archive
    archive_dir = os.path.join(test_index_path, "source_files_archive")
    archived_corrupted = os.path.join(archive_dir, "corruptedPDF_copy.pdf")

    if os.path.exists(archived_corrupted):
        pytest.fail("❌ Le PDF corrompu ne devrait PAS être archivé (il devrait avoir été supprimé)")
    print("   ✅ PDF corrompu non archivé (supprimé comme attendu)")

    # 2. Vérifier que le PDF valide EST dans l'archive
    archived_valid = os.path.join(archive_dir, "validPDF_copy.pdf")
    if not os.path.exists(archived_valid):
        # Lister le contenu de l'archive pour debug
        if os.path.exists(archive_dir):
            print(f"\n   📁 Contenu de {archive_dir}:")
            for item in os.listdir(archive_dir):
                print(f"      - {item}")
        pytest.fail("❌ Le PDF valide devrait être archivé")
    print("   ✅ PDF valide archivé correctement")

    # 3. Vérifier que le markdown du PDF valide a été créé
    md_dir = os.path.join(test_index_path, "md_files")
    valid_md = os.path.join(md_dir, "validPDF_copy.md")
    if not os.path.exists(valid_md):
        # Lister le contenu pour debug
        if os.path.exists(md_dir):
            print(f"\n   📁 Contenu de {md_dir}:")
            for item in os.listdir(md_dir):
                print(f"      - {item}")
        pytest.fail("❌ Le markdown du PDF valide devrait exister")
    print("   ✅ Markdown créé pour le PDF valide")

    # 4. Vérifier que le markdown du PDF corrompu n'existe PAS
    corrupted_md = os.path.join(md_dir, "corruptedPDF_copy.md")
    if os.path.exists(corrupted_md):
        pytest.fail("❌ Le markdown du PDF corrompu ne devrait PAS exister")
    print("   ✅ Aucun markdown pour le PDF corrompu (comme attendu)")

    # 5. Vérifier le nombre de documents indexés dans le statut
    num_docs = status_data.get("num_documents", 0)
    if num_docs != 1:
        pytest.fail(f"❌ Devrait avoir indexé 1 document (le valide), mais a indexé {num_docs}")
    print(f"   ✅ Nombre de documents indexés: {num_docs} (correct)")

    # 6. Vérifier que les nodes du PDF valide sont dans l'index
    index_dir = os.path.join(test_index_path, "index")
    docstore_file = os.path.join(index_dir, "docstore.json")

    if os.path.exists(docstore_file):
        with open(docstore_file, 'r') as f:
            docstore_data = json.load(f)
            num_nodes = len(docstore_data.get("docstore/data", {}))
            print(f"   ✅ Nodes indexés: {num_nodes}")
            if num_nodes == 0:
                pytest.fail("❌ Aucun node trouvé pour le PDF valide")
    else:
        pytest.fail(f"❌ Docstore introuvable: {docstore_file}")

    # 7. Vérifier que le contenu du markdown est correct (pas vide)
    with open(valid_md, 'r', encoding='utf-8') as f:
        md_content = f.read()
        if len(md_content) < 50:
            pytest.fail(f"❌ Le markdown du PDF valide est trop court ({len(md_content)} chars)")
        print(f"   ✅ Markdown du PDF valide contient {len(md_content)} caractères")

    print(f"\n{'=' * 80}")
    print(f"✅ TEST DE VALIDATION PDF RÉUSSI")
    print(f"{'=' * 80}")
    print(f"   📊 Résumé:")
    print(f"      - PDF corrompu : détecté et rejeté ✓")
    print(f"      - PDF corrompu : supprimé du système ✓")
    print(f"      - PDF valide : validé et archivé ✓")
    print(f"      - PDF valide : converti en markdown ✓")
    print(f"      - PDF valide : indexé ({num_nodes} nodes) ✓")
    print(f"{'=' * 80}\n")

    # Cleanup
    if os.path.exists(test_index_path):
        shutil.rmtree(test_index_path)
        print(f"🧹 Nettoyage de l'index de test effectué")


