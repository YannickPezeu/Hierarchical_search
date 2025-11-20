#!/usr/bin/env python3
"""
Script de test pour le système de cache du moteur de recherche.

Usage:
    python test_cache.py

Teste les fonctionnalités suivantes :
1. Cache miss initial
2. Cache hit (RAM)
3. Cache hit (Disque après redémarrage)
4. Normalisation des requêtes
5. Isolation par groupes
6. Statistiques du cache
"""

import sys
import time
from src.core.cache import SearchCache


def print_header(text: str):
    """Affiche un header formaté."""
    print("\n" + "=" * 80)
    print(f" {text}")
    print("=" * 80)


def print_test(text: str):
    """Affiche un test en cours."""
    print(f"\n🧪 TEST: {text}")


def print_success(text: str):
    """Affiche un succès."""
    print(f"   ✅ {text}")


def print_error(text: str):
    """Affiche une erreur."""
    print(f"   ❌ {text}")


def test_cache_basic_operations():
    """Test 1 : Opérations de base du cache."""
    print_header("TEST 1 : Opérations de base")

    cache = SearchCache(max_ram_entries=100)

    # Données de test
    query = "test query"
    index_id = "test_library"
    index_path = "/tmp/test_index"
    user_groups = ["public"]

    results = [
        ("child_1", "parent_1", 0.95),
        ("child_2", "parent_2", 0.89),
        ("child_3", "parent_3", 0.87),
    ]

    # Test : Cache miss initial
    print_test("Cache miss initial")
    cached = cache.get(query, index_id, index_path, user_groups)
    if cached is None:
        print_success("Cache miss détecté correctement")
    else:
        print_error(f"Cache hit inattendu: {cached}")
        return False

    # Test : Écriture dans le cache
    print_test("Écriture dans le cache")
    cache.set(query, index_id, index_path, user_groups, results)
    print_success("Données écrites dans le cache")

    # Test : Cache hit (RAM)
    print_test("Cache hit (RAM)")
    cached = cache.get(query, index_id, index_path, user_groups)
    if cached == results:
        print_success(f"Cache hit RAM réussi : {len(cached)} résultats")
    else:
        print_error(f"Données incorrectes: {cached}")
        return False

    return True


def test_query_normalization():
    """Test 2 : Normalisation des requêtes."""
    print_header("TEST 2 : Normalisation des requêtes")

    cache = SearchCache(max_ram_entries=100)

    index_id = "test_library"
    index_path = "/tmp/test_index"
    user_groups = ["public"]
    results = [("child_1", "parent_1", 0.95)]

    # Variantes de la même requête
    queries = [
        "machine learning",
        "Machine Learning",
        "MACHINE LEARNING",
        "  machine   learning  ",
        "machine  learning",
    ]

    print_test("Test de normalisation avec variantes")

    # Écrire avec la première variante
    cache.set(queries[0], index_id, index_path, user_groups, results)
    print_success(f"Cache écrit avec : '{queries[0]}'")

    # Tester toutes les variantes
    for i, query in enumerate(queries[1:], 1):
        cached = cache.get(query, index_id, index_path, user_groups)
        if cached == results:
            print_success(f"Variante {i} trouvée : '{query}'")
        else:
            print_error(f"Variante {i} non trouvée : '{query}'")
            return False

    return True


def test_group_isolation():
    """Test 3 : Isolation par groupes utilisateurs."""
    print_header("TEST 3 : Isolation par groupes")

    cache = SearchCache(max_ram_entries=100)

    query = "sensitive data"
    index_id = "test_library"
    index_path = "/tmp/test_index"

    # Différents groupes
    admin_groups = ["admin", "dev"]
    user_groups = ["user"]
    public_groups = ["public"]

    admin_results = [("admin_child", "admin_parent", 0.95)]
    user_results = [("user_child", "user_parent", 0.85)]

    print_test("Écriture avec groupes admin")
    cache.set(query, index_id, index_path, admin_groups, admin_results)
    print_success("Données admin écrites")

    print_test("Écriture avec groupes user")
    cache.set(query, index_id, index_path, user_groups, user_results)
    print_success("Données user écrites")

    # Vérifier l'isolation
    print_test("Vérification de l'isolation")

    admin_cached = cache.get(query, index_id, index_path, admin_groups)
    if admin_cached == admin_results:
        print_success("Groupes admin : Cache isolé correctement")
    else:
        print_error(f"Groupes admin : Isolation échouée - {admin_cached}")
        return False

    user_cached = cache.get(query, index_id, index_path, user_groups)
    if user_cached == user_results:
        print_success("Groupes user : Cache isolé correctement")
    else:
        print_error(f"Groupes user : Isolation échouée - {user_cached}")
        return False

    public_cached = cache.get(query, index_id, index_path, public_groups)
    if public_cached is None:
        print_success("Groupes public : Aucun cache (attendu)")
    else:
        print_error(f"Groupes public : Cache inattendu - {public_cached}")
        return False

    return True


def test_lru_eviction():
    """Test 4 : Éviction LRU du cache RAM."""
    print_header("TEST 4 : Éviction LRU")

    # Cache avec seulement 3 entrées
    cache = SearchCache(max_ram_entries=3)

    index_id = "test_library"
    index_path = "/tmp/test_index"
    user_groups = ["public"]

    print_test("Remplissage du cache (3 entrées max)")

    # Remplir le cache
    for i in range(5):
        query = f"query_{i}"
        results = [(f"child_{i}", f"parent_{i}", 0.9)]
        cache.set(query, index_id, index_path, user_groups, results)
        print_success(f"Entrée {i} écrite")

    print_test("Vérification des évictions LRU")

    # Les 2 premières requêtes devraient avoir été évincées
    for i in range(2):
        query = f"query_{i}"
        cached = cache.get(query, index_id, index_path, user_groups)
        if cached is None:
            print_success(f"Entrée {i} évincée (attendu)")
        else:
            print_error(f"Entrée {i} toujours présente")
            return False

    # Les 3 dernières devraient être présentes
    for i in range(2, 5):
        query = f"query_{i}"
        cached = cache.get(query, index_id, index_path, user_groups)
        if cached is not None:
            print_success(f"Entrée {i} présente (attendu)")
        else:
            print_error(f"Entrée {i} absente")
            return False

    return True


def test_score_rounding():
    """Test 5 : Arrondissement des scores."""
    print_header("TEST 5 : Arrondissement des scores")

    cache = SearchCache(max_ram_entries=100)

    query = "test query"
    index_id = "test_library"
    index_path = "/tmp/test_index"
    user_groups = ["public"]

    # Scores avec beaucoup de décimales
    results_input = [
        ("child_1", "parent_1", 0.9523456789),
        ("child_2", "parent_2", 0.8912345678),
        ("child_3", "parent_3", 0.8734567890),
    ]

    # Scores attendus (arrondis à 2 décimales)
    results_expected = [
        ("child_1", "parent_1", 0.95),
        ("child_2", "parent_2", 0.89),
        ("child_3", "parent_3", 0.87),
    ]

    print_test("Écriture avec scores à haute précision")
    cache.set(query, index_id, index_path, user_groups, results_input)
    print_success("Scores écrits")

    print_test("Vérification de l'arrondissement")
    cached = cache.get(query, index_id, index_path, user_groups)

    if cached == results_expected:
        print_success("Scores correctement arrondis à 2 décimales")
        for i, (inp, exp) in enumerate(zip(results_input, cached)):
            print(f"      Entrée {i}: {inp[2]:.10f} → {exp[2]}")
    else:
        print_error(f"Arrondissement incorrect: {cached}")
        return False

    return True


def test_cache_statistics():
    """Test 6 : Statistiques du cache."""
    print_header("TEST 6 : Statistiques")

    cache = SearchCache(max_ram_entries=100)

    index_id = "test_library"
    index_path = "/tmp/test_index"
    user_groups = ["public"]
    results = [("child_1", "parent_1", 0.95)]

    print_test("Initialisation des stats")
    stats = cache.get_stats()
    print_success(f"Stats initiales : {stats}")

    print_test("Génération d'activité")

    # Miss
    cache.get("query_1", index_id, index_path, user_groups)
    print_success("Cache miss enregistré")

    # Write + Hit
    cache.set("query_1", index_id, index_path, user_groups, results)
    cache.get("query_1", index_id, index_path, user_groups)
    print_success("Cache write + hit enregistrés")

    print_test("Vérification des statistiques finales")
    stats = cache.get_stats()

    expected = {
        "ram_hits": 1,
        "disk_hits": 0,
        "misses": 1,
        "writes": 1
    }

    if stats == expected:
        print_success(f"Statistiques correctes : {stats}")
    else:
        print_error(f"Statistiques incorrectes:")
        print(f"      Attendu : {expected}")
        print(f"      Reçu    : {stats}")
        return False

    return True


def run_all_tests():
    """Exécute tous les tests."""
    print_header("TESTS DU SYSTÈME DE CACHE")

    tests = [
        ("Opérations de base", test_cache_basic_operations),
        ("Normalisation des requêtes", test_query_normalization),
        ("Isolation par groupes", test_group_isolation),
        ("Éviction LRU", test_lru_eviction),
        ("Arrondissement des scores", test_score_rounding),
        ("Statistiques", test_cache_statistics),
    ]

    results = []
    start_time = time.time()

    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print_error(f"Exception dans le test : {e}")
            results.append((name, False))

    # Résumé
    print_header("RÉSUMÉ DES TESTS")

    total = len(results)
    passed = sum(1 for _, success in results if success)
    failed = total - passed

    for name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status} : {name}")

    print(f"\n📊 Résultats : {passed}/{total} tests réussis")

    elapsed = time.time() - start_time
    print(f"⏱️  Durée totale : {elapsed:.2f}s")

    if failed > 0:
        print(f"\n❌ {failed} test(s) échoué(s)")
        sys.exit(1)
    else:
        print("\n✅ Tous les tests ont réussi !")
        sys.exit(0)


if __name__ == "__main__":
    run_all_tests()