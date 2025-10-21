# Guide de configuration des permissions des bibliothèques

## Structure des fichiers `.groups.json`

Chaque bibliothèque doit avoir un fichier `.groups.json` dans son dossier racine :
```
all_indexes/
├── ma_bibliotheque/
│   ├── .groups.json      ← Fichier de permissions
│   ├── index/
│   ├── source_files/
│   └── source_files_archive/
```

## Formats de configuration

### 1. Bibliothèque privée (groupes spécifiques)
```json
{
  "groups": ["admin", "data-science-team", "managers"]
}
```
➡️ Seuls les utilisateurs appartenant à ces groupes peuvent accéder

### 2. Bibliothèque publique (accessible à tous)
```json
{
  "groups": ["public"]
}
```
➡️ Tous les utilisateurs ont accès, même sans groupes

### 3. Pas de fichier `.groups.json`
➡️ La bibliothèque est considérée comme **publique par défaut** (legacy)

## Exemples de cas d'usage

### Cas 1 : Bibliothèque d'entreprise réservée aux RH
```json
{
  "groups": ["hr-department", "hr-managers", "ceo"]
}
```

### Cas 2 : Documentation générale accessible à tous
```json
{
  "groups": ["public"]
}
```

### Cas 3 : Projet avec plusieurs équipes
```json
{
  "groups": ["project-alpha-dev", "project-alpha-pm", "executives"]
}
```

### Cas 4 : Bibliothèque mixte (publique + groupes privés)
```json
{
  "groups": ["public"]
}
```
**Note** : Si `"public"` est présent, tous les autres groupes sont ignorés car la bibliothèque devient accessible à tous.

## Vérification des permissions

### Comment ça marche ?

1. **L'utilisateur envoie ses groupes** :
   ```
   GET /libraries?user_groups=team-a,team-b,managers
   ```

2. **Pour chaque bibliothèque** :
   - Lire le fichier `.groups.json`
   - Si `"public"` est dans les groupes → ✅ Accès accordé
   - Sinon, vérifier si un groupe de l'utilisateur correspond → ✅ Accès accordé
   - Sinon → ❌ Accès refusé

3. **Exemples** :

| Utilisateur a les groupes | Bibliothèque autorise | Résultat |
|---------------------------|----------------------|----------|
| `["team-a", "managers"]` | `["team-a", "team-b"]` | ✅ Accès (match sur `team-a`) |
| `["team-c"]` | `["team-a", "team-b"]` | ❌ Refusé (aucun match) |
| `["team-c"]` | `["public"]` | ✅ Accès (bibliothèque publique) |
| `[]` (aucun groupe) | `["public"]` | ✅ Accès (bibliothèque publique) |
| `[]` (aucun groupe) | `["team-a"]` | ❌ Refusé |

## Création/Modification des permissions

### Via l'API (lors de l'indexation)
```python
import requests

files = [("files", open("document.pdf", "rb"))]
data = {
    "groups": json.dumps(["team-alpha", "executives"])  # ← Définir les groupes
}
headers = {"X-API-Key": "votre-clé"}

requests.post(
    "http://localhost:8000/index/ma_bibliotheque",
    files=files,
    data=data,
    headers=headers
)
```

### Manuellement
```bash
cd all_indexes/ma_bibliotheque
echo '{"groups": ["public"]}' > .groups.json
```

## Recommandations

1. **Toujours définir les groupes** lors de la création d'une bibliothèque
2. Utiliser `"public"` pour les documentations générales
3. Utiliser des noms de groupes descriptifs (`hr-team`, `finance-dept`, etc.)
4. Documenter les groupes utilisés dans votre organisation
5. Tester les permissions après chaque modification

## Résolution de problèmes

### Une bibliothèque n'apparaît pas dans la liste ?
- Vérifier que le fichier `.groups.json` existe et est valide
- Vérifier que l'utilisateur a au moins un groupe correspondant
- Vérifier les logs du serveur

### Comment rendre une bibliothèque privée publique ?
```bash
cd all_indexes/ma_bibliotheque
echo '{"groups": ["public"]}' > .groups.json
```

### Comment restreindre une bibliothèque publique ?
```bash
cd all_indexes/ma_bibliotheque
echo '{"groups": ["admin", "trusted-users"]}' > .groups.json
```