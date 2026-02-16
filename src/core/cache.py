# src/core/cache.py
import os
import json
import hashlib
import logging
from typing import List, Dict, Optional, Tuple
from collections import OrderedDict
from threading import Lock

logger = logging.getLogger(__name__)


class SearchCache:
    """
    Gestionnaire de cache pour les recherches avec double couche (RAM + Disque).

    Stockage optimisé :
    - Clé : hash de (query normalisée, index_id, user_groups triés)
    - Valeur : liste de tuples (child_node_id, parent_node_id, score_arrondi)

    Avec cette structure, une requête cachée pèse ~500 bytes (15 résultats × 2 IDs × 16 chars + scores)
    → 1 Go = ~2 millions de requêtes cachées !
    """

    def __init__(self, max_ram_entries: int = 10000):
        """
        Args:
            max_ram_entries: Nombre maximum d'entrées en RAM (LRU)
        """
        self.max_ram_entries = max_ram_entries
        self.ram_cache: OrderedDict[str, List[Tuple[str, str, float]]] = OrderedDict()
        self.lock = Lock()
        self.stats = {
            "ram_hits": 0,
            "disk_hits": 0,
            "misses": 0,
            "writes": 0
        }

    def _normalize_query(self, query: str) -> str:
        """
        Normalise la requête pour augmenter les cache hits.

        Transformations :
        - Lowercase
        - Strip whitespace
        - Normalisation des espaces multiples
        """
        query = query.lower().strip()
        query = " ".join(query.split())  # Normaliser les espaces multiples
        return query

    def _generate_cache_key(self, query: str, index_id: str, user_groups: List[str], url_filter: Optional[str] = None) -> str:
        """
        Génère une clé de cache unique et reproductible.

        Format: hash(query_normalisée + index_id + user_groups_triés + url_filter)
        """
        normalized_query = self._normalize_query(query)

        # Trier les groupes pour éviter les duplicatas dus à l'ordre
        sorted_groups = sorted(user_groups)
        groups_str = ",".join(sorted_groups)

        # Créer la chaîne à hasher
        filter_str = url_filter.strip("/") if url_filter else ""
        cache_string = f"{normalized_query}|{index_id}|{groups_str}|{filter_str}"

        # Utiliser SHA256 pour éviter les collisions (plus court que MD5 suffit)
        cache_key = hashlib.sha256(cache_string.encode()).hexdigest()[:16]  # 16 chars suffisent

        return cache_key

    def _get_cache_file_path(self, index_path: str) -> str:
        """
        Retourne le chemin du fichier cache pour un index donné.

        Args:
            index_path: Chemin du dossier de l'index

        Returns:
            Chemin complet vers cache.json
        """
        return os.path.join(index_path, "cache.json")

    def _round_score(self, score: float) -> float:
        """Arrondit le score à 2 décimales pour optimiser le stockage."""
        return round(score, 2)

    def get(
            self,
            query: str,
            index_id: str,
            index_path: str,
            user_groups: List[str],
            url_filter: Optional[str] = None
    ) -> Optional[List[Tuple[str, str, float]]]:
        """
        Récupère les résultats cachés pour une requête.

        Stratégie :
        1. Chercher dans le cache RAM (très rapide)
        2. Si non trouvé, chercher dans le fichier disque
        3. Si trouvé sur disque, charger dans RAM

        Args:
            query: La requête de recherche
            index_id: ID de la bibliothèque
            index_path: Chemin du dossier de l'index
            user_groups: Groupes de l'utilisateur
            url_filter: URL path prefix filter (included in cache key)

        Returns:
            Liste de tuples (child_node_id, parent_node_id, score) ou None si non trouvé
        """
        cache_key = self._generate_cache_key(query, index_id, user_groups, url_filter)

        # ========================================
        # ÉTAPE 1 : Chercher dans le cache RAM
        # ========================================
        with self.lock:
            if cache_key in self.ram_cache:
                # Déplacer en fin de OrderedDict (LRU)
                self.ram_cache.move_to_end(cache_key)
                result = self.ram_cache[cache_key]
                self.stats["ram_hits"] += 1
                logger.info(f"💾 Cache RAM HIT for query: '{query[:50]}...' (key: {cache_key})")
                return result

        # ========================================
        # ÉTAPE 2 : Chercher dans le fichier disque
        # ========================================
        cache_file = self._get_cache_file_path(index_path)

        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    disk_cache = json.load(f)

                if cache_key in disk_cache:
                    # Convertir les listes en tuples
                    result = [tuple(item) for item in disk_cache[cache_key]]

                    # Charger dans le cache RAM pour les prochaines fois
                    with self.lock:
                        self._add_to_ram_cache(cache_key, result)

                    self.stats["disk_hits"] += 1
                    logger.info(f"💿 Cache DISK HIT for query: '{query[:50]}...' (key: {cache_key})")
                    return result

            except Exception as e:
                logger.error(f"❌ Error reading cache file {cache_file}: {e}")

        # ========================================
        # Cache miss
        # ========================================
        self.stats["misses"] += 1
        logger.debug(f"🔍 Cache MISS for query: '{query[:50]}...' (key: {cache_key})")
        return None

    def _add_to_ram_cache(self, cache_key: str, result: List[Tuple[str, str, float]]):
        """
        Ajoute une entrée au cache RAM avec gestion LRU.

        Thread-safe (doit être appelé avec self.lock acquis).
        """
        # Ajouter la nouvelle entrée
        self.ram_cache[cache_key] = result

        # Si la limite est dépassée, supprimer les plus anciennes
        while len(self.ram_cache) > self.max_ram_entries:
            # OrderedDict : popitem(last=False) retire le plus ancien
            oldest_key, _ = self.ram_cache.popitem(last=False)
            logger.debug(f"🗑️  Evicting old cache entry from RAM: {oldest_key}")

    def set(
            self,
            query: str,
            index_id: str,
            index_path: str,
            user_groups: List[str],
            results: List[Tuple[str, str, float]],
            url_filter: Optional[str] = None
    ):
        """
        Sauvegarde les résultats dans le cache (RAM + Disque).

        Args:
            query: La requête de recherche
            index_id: ID de la bibliothèque
            index_path: Chemin du dossier de l'index
            user_groups: Groupes de l'utilisateur
            results: Liste de tuples (child_node_id, parent_node_id, score)
            url_filter: URL path prefix filter (included in cache key)
        """
        cache_key = self._generate_cache_key(query, index_id, user_groups, url_filter)

        # Arrondir les scores
        rounded_results = [
            (child_id, parent_id, self._round_score(score))
            for child_id, parent_id, score in results
        ]

        # ========================================
        # ÉTAPE 1 : Sauvegarder dans le cache RAM
        # ========================================
        with self.lock:
            self._add_to_ram_cache(cache_key, rounded_results)

        # ========================================
        # ÉTAPE 2 : Sauvegarder dans le fichier disque
        # ========================================
        cache_file = self._get_cache_file_path(index_path)

        try:
            # Charger le cache existant
            if os.path.exists(cache_file):
                with open(cache_file, "r") as f:
                    disk_cache = json.load(f)
            else:
                disk_cache = {}

            # Ajouter la nouvelle entrée
            disk_cache[cache_key] = rounded_results

            # Sauvegarder (écriture atomique via fichier temporaire)
            temp_file = cache_file + ".tmp"
            with open(temp_file, "w") as f:
                json.dump(disk_cache, f, separators=(',', ':'))  # Compact JSON

            # Renommer atomiquement
            os.replace(temp_file, cache_file)

            self.stats["writes"] += 1
            logger.debug(f"💾 Cached query: '{query[:50]}...' (key: {cache_key}, {len(rounded_results)} results)")

        except Exception as e:
            logger.error(f"❌ Error writing to cache file {cache_file}: {e}")

    def clear_index_cache(self, index_path: str):
        """
        Efface le cache disque d'un index spécifique.

        Utilisé lors de la réindexation d'une bibliothèque.
        """
        cache_file = self._get_cache_file_path(index_path)

        if os.path.exists(cache_file):
            try:
                os.remove(cache_file)
                logger.info(f"🗑️  Cleared cache file: {cache_file}")
            except Exception as e:
                logger.error(f"❌ Error clearing cache file {cache_file}: {e}")

        # Nettoyer aussi le cache RAM pour cet index
        with self.lock:
            # Note : On ne peut pas facilement identifier les clés par index_id sans les décoder
            # Alternative : on pourrait ajouter un préfixe index_id dans les clés
            # Pour l'instant, on laisse le cache RAM se purger naturellement (LRU)
            pass

    def get_stats(self) -> Dict[str, int]:
        """Retourne les statistiques du cache."""
        return self.stats.copy()

    def clear_all_ram(self):
        """Vide complètement le cache RAM."""
        with self.lock:
            self.ram_cache.clear()
        logger.info("🗑️  Cleared all RAM cache")


# Instance globale du cache
search_cache = SearchCache(max_ram_entries=10000)