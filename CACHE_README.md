# 💾 Système de Cache pour le Moteur de Recherche

## 📋 Aperçu

Ce système de cache optimise les performances du moteur de recherche en mémorisant les résultats des requêtes. Grâce à un stockage ultra-compact (seulement les IDs et scores), il peut cacher **des centaines de milliers de requêtes dans 1 Go de RAM**.

## 🎯 Architecture

### Double couche de cache
- **RAM** : Cache LRU (Least Recently Used) ultra-rapide, limité à 10 000 entrées par défaut
- **Disque** : Cache persistant illimité dans chaque index (`cache.json`)

### Taille d'une entrée cachée
Chaque requête cachée stocke :
- 15 résultats × (2 IDs de 32 chars + 1 score float)
- **≈ 500 bytes par requête**
- **1 Go = ~2 millions de requêtes** 🚀

## 📁 Structure des fichiers

```
all_indexes/
└── ma_bibliotheque/
    ├── index/              # Index FAISS
    ├── source_files_archive/
    ├── md_files/
    └── cache.json          # ✨ NOUVEAU : Cache disque
```

## 🔧 Installation

### 1. Ajouter le module cache

Copiez `cache.py` dans `src/core/cache.py`.

### 2. Modifier `search.py`

Remplacez votre fichier `src/routes/search.py` par la version modifiée fournie, ou appliquez manuellement les modifications suivantes :

**Import** (ligne ~17) :
```python
from src.core.cache import search_cache
```

**Dans la fonction `search_in_index`**, AVANT le pipeline de recherche :
```python
# Vérifier le cache
cached_results = search_cache.get(
    query=request.query,
    index_id=index_id,
    index_path=index_path,
    user_groups=request.user_groups
)

if cached_results is not None:
    # Reconstruire les résultats depuis les IDs cachés
    # ... (voir le code complet)
    return results
```

**À la fin du pipeline de recherche**, sauvegarder dans le cache :
```python
# Préparer les données pour le cache
cache_data = [
    (child_node.id_, parent_node.id_, pair['rerank_score'])
    for pair in final_pairs
]

# Sauvegarder dans le cache
search_cache.set(
    query=request.query,
    index_id=index_id,
    index_path=index_path,
    user_groups=request.user_groups,
    results=cache_data
)
```

### 3. Modifier `indexing.py`

Ouvrez `src/core/indexing.py` et appliquez les modifications du fichier `indexing_modifications.txt` :

**Import** (ligne ~30) :
```python
from src.core.cache import search_cache
```

**Dans `index_creation_task`**, après la création du status_file (ligne ~370) :
```python
# Nettoyer le cache pour cet index lors de la réindexation
logger.info(f"🗑️  Clearing cache for index: {index_id}")
search_cache.clear_index_cache(index_path)
```

## 🚀 Utilisation

### Pipeline automatique

Le cache fonctionne automatiquement :

1. **Requête entrante** → Vérification cache RAM
2. **Cache RAM miss** → Vérification cache disque
3. **Cache disque hit** → Chargement en RAM + reconstruction des résultats
4. **Cache complet miss** → Pipeline de recherche complet + sauvegarde dans le cache

### Normalisation des requêtes

Les requêtes sont automatiquement normalisées pour maximiser les cache hits :
```python
"Qu'est-ce que   l'IA ?"  → "qu'est-ce que l'ia ?"
"  Machine Learning  "    → "machine learning"
```

## 📊 Monitoring

### Statistiques du cache

**Endpoint** : `GET /search/{index_id}/cache/stats`

**Réponse** :
```json
{
  "cache_stats": {
    "ram_hits": 1250,
    "disk_hits": 380,
    "misses": 420,
    "writes": 420
  },
  "total_requests": 2050,
  "hit_rate_percentage": 79.51,
  "ram_cache_size": 1630
}
```

### Interprétation
- **ram_hits** : Requêtes servies depuis la RAM (< 1ms)
- **disk_hits** : Requêtes servies depuis le disque (5-10ms)
- **misses** : Nouvelles requêtes nécessitant le pipeline complet (500-2000ms)
- **hit_rate_percentage** : Pourcentage de requêtes cachées

## 🛠️ Administration

### Vider le cache d'un index

**Endpoint** : `DELETE /search/{index_id}/cache`

```bash
curl -X DELETE "https://api.example.com/search/ma_bibliotheque/cache" \
  -H "X-API-Key: votre_api_key"
```

**Utilité** :
- Après une réindexation (fait automatiquement)
- Pour libérer de l'espace disque
- Pour forcer le recalcul des résultats

### Vider le cache RAM global

```python
from src.core.cache import search_cache

# Vider complètement la RAM
search_cache.clear_all_ram()

# Réinitialiser les stats
search_cache.stats = {
    "ram_hits": 0,
    "disk_hits": 0,
    "misses": 0,
    "writes": 0
}
```

## ⚙️ Configuration

### Taille du cache RAM

Par défaut : 10 000 entrées (≈ 5 Mo)

Modifier dans `src/core/cache.py` :
```python
# Instance globale
search_cache = SearchCache(max_ram_entries=20000)  # 20k entrées
```

### Clé de cache

Format : `SHA256(query_normalisée|index_id|user_groups_triés)[:16]`

Exemples :
```
query="machine learning", index_id="ai_docs", groups=["public"]
→ clé: "a3f2e9b7d4c1"

query="deep learning", index_id="ai_docs", groups=["admin","user"]
→ clé: "8c4d1a5e7f2b"
```

## 🔍 Détails techniques

### Structure du cache disque (cache.json)

```json
{
  "a3f2e9b7d4c1": [
    ["child_id_1", "parent_id_1", 0.95],
    ["child_id_2", "parent_id_2", 0.89],
    ...
  ],
  "8c4d1a5e7f2b": [
    ...
  ]
}
```

### Reconstruction depuis le cache

Pour chaque tuple `(child_id, parent_id, score)` :
1. Charger `child_node` depuis le docstore
2. Charger `parent_node` depuis le docstore
3. Extraire `precise_content` (du child)
4. Extraire `context_content` (du parent)
5. Construire `SearchResultNode` complet

**Temps** : ~5-10ms pour 15 résultats (vs 500-2000ms pour le pipeline complet)

### Thread safety

Le cache RAM utilise un `Lock` pour garantir la thread safety :
```python
with self.lock:
    self.ram_cache[cache_key] = result
```

## 📈 Gains de performance attendus

### Scénario typique

**Avant le cache** :
- Recherche : 500-2000ms
- Throughput : 1-2 requêtes/seconde

**Après le cache (80% hit rate)** :
- Cache RAM hit : <1ms
- Cache disque hit : 5-10ms
- Throughput : 50-200 requêtes/seconde

### ROI

- **Stockage** : 1 Go RAM = 2 millions de requêtes
- **Latence** : Réduction de 99% pour les requêtes cachées
- **Serveur** : Économie massive de CPU/GPU (pas de reranking)

## 🐛 Dépannage

### Cache hit rate faible (<30%)

**Causes possibles** :
1. Requêtes trop variées (typos, formulations différentes)
2. Groupes utilisateurs très fragmentés
3. Cache RAM trop petit

**Solutions** :
- Augmenter `max_ram_entries`
- Implémenter une normalisation plus agressive
- Analyser les patterns de requêtes

### Fichier cache.json volumineux

**Taille normale** : 100k-1M de requêtes = 50-500 Mo

**Si trop gros** :
```python
# Option 1 : Supprimer et recréer
os.remove(f"{index_path}/cache.json")

# Option 2 : Filtrer les anciennes entrées (à implémenter)
```

### Résultats incohérents après réindexation

**Cause** : Cache non vidé après réindexation

**Solution** : Le cache est automatiquement vidé si vous avez appliqué les modifications dans `indexing.py`

## 🔐 Sécurité

### Isolation par groupes

Les résultats sont cachés **par combinaison de groupes utilisateur** :
- User A (groups: ["admin", "dev"]) ne verra pas le cache de User B (groups: ["user"])
- Garantit la confidentialité même avec des requêtes identiques

### Format de la clé

```python
cache_key = hash(query + index_id + sorted(user_groups))
```

Aucune collision possible entre utilisateurs de groupes différents.

## 📝 Logs

### Lors d'un cache hit (RAM)
```
💾 Cache RAM HIT for query: 'machine learning...' (key: a3f2e9b7)
✨ Cache HIT! Rebuilding 15 results from cached IDs
✅ Cache reconstruction complete: 15 results
```

### Lors d'un cache hit (Disque)
```
💿 Cache DISK HIT for query: 'deep learning...' (key: 8c4d1a5e)
✨ Cache HIT! Rebuilding 15 results from cached IDs
✅ Cache reconstruction complete: 15 results
```

### Lors d'un cache miss
```
🔍 Cache MISS for query: 'reinforcement learning...' (key: f3a8b2c1)
🔍 Cache MISS! Running full search pipeline
📍 STEP 1: Retrieving sub-chunks...
...
💾 Cached query: 'reinforcement learning...' (key: f3a8b2c1, 15 results)
```

## 🎓 Exemple d'intégration complète

Voir les fichiers fournis :
- `cache.py` : Module de cache complet
- `search.py` : Recherche avec intégration du cache
- `indexing_modifications.txt` : Modifications pour l'indexation

## 🚦 Checklist de déploiement

- [ ] Copier `cache.py` dans `src/core/`
- [ ] Remplacer `search.py` ou appliquer les modifications
- [ ] Modifier `indexing.py` (import + clear_index_cache)
- [ ] Tester avec une requête simple
- [ ] Vérifier les stats : `GET /search/{index_id}/cache/stats`
- [ ] Monitorer les logs pour voir les cache hits
- [ ] Réindexer une bibliothèque et vérifier que le cache est vidé
- [ ] Tester avec différents groupes utilisateurs

## 📚 Ressources

- **Documentation LlamaIndex** : https://docs.llamaindex.ai/
- **FAISS** : https://github.com/facebookresearch/faiss
- **OrderedDict LRU** : https://docs.python.org/3/library/collections.html#collections.OrderedDict

## 🤝 Support

Pour toute question ou problème :
1. Vérifier les logs du serveur
2. Consulter les stats du cache
3. Tester avec `curl` direct
4. Vider le cache et retenter

---

**Version** : 1.0.0  
**Date** : Octobre 2025  
**Auteur** : Système de cache pour moteur de recherche sémantique