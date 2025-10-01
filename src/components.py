# src/components.py (VERSION FINALE CORRIGÉE)
import re
import urllib.parse

import unicodedata
from llama_index.core.schema import TransformComponent, NodeWithScore, QueryBundle, NodeRelationship, RelatedNodeInfo, TextNode
from llama_index.core.postprocessor.types import BaseNodePostprocessor # Votre import correct
from typing import List, Optional
from llama_index.core.storage.docstore.types import BaseDocumentStore
from collections import Counter # <--- IMPORTATION AJOUTÉE

# La classe FilterEmptyNodes est déjà correcte
class FilterEmptyNodes(TransformComponent):
    min_length: int
    min_lines: int
    def __call__(self, nodes, **kwargs):
        initial_count = len(nodes)
        filtered_nodes = [
            n for n in nodes 
            if len(n.text) > self.min_length and len(n.text.splitlines()) >= self.min_lines
        ]
        print(f"Filtrage des nodes vides : {initial_count} -> {len(filtered_nodes)} nodes")
        return filtered_nodes

# --- LA CORRECTION EST DANS CETTE CLASSE ---
class RepairRelationships(TransformComponent):
    """Met à jour les relations prev/next après qu'un filtre ait retiré des nodes."""
    def __call__(self, nodes, **kwargs):
        for i, node in enumerate(nodes):
            # Réparer le lien précédent en modifiant le dictionnaire relationships
            if i > 0:
                node.relationships[NodeRelationship.PREVIOUS] = RelatedNodeInfo(node_id=nodes[i-1].id_)
            elif NodeRelationship.PREVIOUS in node.relationships:
                del node.relationships[NodeRelationship.PREVIOUS]
            
            # Réparer le lien suivant de la même manière
            if i < len(nodes) - 1:
                node.relationships[NodeRelationship.NEXT] = RelatedNodeInfo(node_id=nodes[i+1].id_)
            elif NodeRelationship.NEXT in node.relationships:
                del node.relationships[NodeRelationship.NEXT]

        print(f"Relations de voisinage réparées pour {len(nodes)} nodes.")
        return nodes

# La classe AddBreadcrumbs est déjà correcte
class AddBreadcrumbs_bu(BaseNodePostprocessor):
    def _postprocess_nodes(self, nodes: List[NodeWithScore], query_bundle: Optional[QueryBundle] = None) -> List[NodeWithScore]:
        for n in nodes:
            header_keys = sorted([key for key in n.node.metadata.keys() if key.startswith("Header")])
            if header_keys:
                breadcrumbs = " > ".join([n.node.metadata[key] for key in header_keys])
                file_name = n.node.metadata.get("file_name", "Document")
                n.node.set_content(f"Source: {file_name}\nContexte: {breadcrumbs}\n---\n{n.node.get_content()}")
        return nodes


# src/components.py

class AddBreadcrumbs(BaseNodePostprocessor):
    def _postprocess_nodes(self, nodes: List[NodeWithScore], query_bundle: Optional[QueryBundle] = None) -> List[
        NodeWithScore]:

        # ▼▼▼ LIGNES DE DÉBOGAGE À AJOUTER ▼▼▼

        print("\n--- 🕵️‍♀️ Inspection des métadonnées dans AddBreadcrumbs ---")
        for i, n in enumerate(nodes):
            print(f"\n[INFO] Métadonnées du Node #{i}:")
            # Affiche toutes les métadonnées du node actuel
            print(n.node.metadata)

            # Votre code original reste ici pour voir s'il s'exécute
            header_keys = sorted([key for key in n.node.metadata.keys() if key.startswith("Header")])

            if header_keys:
                print(f"  [✅ SUCCÈS] Headers trouvés: {header_keys}")
                breadcrumbs = " > ".join([n.node.metadata[key] for key in header_keys])
                file_name = n.node.metadata.get("file_name", "Document")
                n.node.set_content(f"Source: {file_name}\nContexte: {breadcrumbs}\n---\n{n.node.get_content()}")
            else:
                print("  [⚠️ ALERTE] Aucun 'Header' trouvé dans les métadonnées de ce node.")

        print("--- Fin de l'inspection ---")

        # ▲▲▲ FIN DES LIGNES DE DÉBOGAGE ▲▲▲

        return nodes


from llama_index.core.schema import TextNode


# Assurez-vous d'avoir tous les imports nécessaires en haut de votre fichier
# from llama_index.core.postprocessor.types import BaseNodePostprocessor
# from llama_index.core.schema import NodeWithScore, QueryBundle
# from llama_index.core.storage.docstore.types import BaseDocumentStore
# from typing import List, Optional

class ContextMerger(BaseNodePostprocessor):
    """
    Fusionne chaque node avec ses voisins (précédent et suivant)
    pour créer un seul node de contexte étendu.
    """
    docstore: BaseDocumentStore

    def _postprocess_nodes(self, nodes: List[NodeWithScore], query_bundle: Optional[QueryBundle] = None) -> List[
        NodeWithScore]:
        if not nodes:
            return []

        docstore = self.docstore
        merged_nodes = []

        for node_with_score in nodes:
            original_node = node_with_score.node

            # Récupérer les textes des voisins
            prev_text = docstore.get_node(
                original_node.prev_node.node_id).get_content() if original_node.prev_node else ""
            next_text = docstore.get_node(
                original_node.next_node.node_id).get_content() if original_node.next_node else ""

            # Concaténer les textes
            merged_text = f"{prev_text}\n\n---\n\n{original_node.get_content()}\n\n---\n\n{next_text}".strip()

            # ▼▼▼ MODIFICATION ▼▼▼
            # On copie les métadonnées pour ne pas modifier l'original
            new_metadata = original_node.metadata.copy()
            # On ajoute l'ID original dans les métadonnées du nouveau noeud
            new_metadata['original_node_id'] = original_node.node_id

            # Créer un nouveau node fusionné en utilisant les nouvelles métadonnées
            merged_node = NodeWithScore(
                node=TextNode(
                    text=merged_text,
                    metadata=new_metadata  # Utilisation des métadonnées enrichies
                ),
                score=node_with_score.score  # On garde le score du node central
            )
            # ▲▲▲ FIN DE LA MODIFICATION ▲▲▲
            merged_nodes.append(merged_node)

        return merged_nodes

def remove_duplicate_headers(markdown_text: str) -> str:
    # Cette fonction reste utile car unstructured peut aussi extraire des en-têtes répétitifs.
    lines = markdown_text.splitlines()
    headers = [line.strip() for line in lines if line.strip().startswith("#")]
    header_counts = Counter(headers)
    duplicate_headers = {header for header, count in header_counts.items() if count > 1}
    cleaned_lines = []
    seen_duplicates = set()
    for line in lines:
        stripped_line = line.strip()
        if stripped_line in duplicate_headers:
            if stripped_line in seen_duplicates:
                continue
            else:
                seen_duplicates.add(stripped_line)
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


import re
import unicodedata
import urllib.parse
import os

def normalize_filename(filename: str) -> str:
    """
    Normalise un nom de fichier de manière universelle et sûre pour les URLs.
    Remplace TOUS les caractères non-ASCII par leur équivalent ASCII ou underscore.
    """
    # Étape 1: Décoder les caractères d'URL si présents
    if '%' in filename:
        name = urllib.parse.unquote(filename)
    else:
        name = filename

    # Étape 2: Séparer le nom et l'extension
    base_name, extension = os.path.splitext(name)

    # Étape 3: Convertir les caractères Unicode en ASCII (ü -> u, é -> e, etc.)
    base_name = unicodedata.normalize('NFKD', base_name)
    base_name = base_name.encode('ascii', 'ignore').decode('ascii')

    # Étape 4: Remplacer les espaces par des underscores
    base_name = base_name.replace(" ", "_")

    # Étape 5: Ne garder que alphanumériques, points, underscores et tirets
    base_name = re.sub(r'[^a-zA-Z0-9._-]', '_', base_name)

    # Étape 6: Réduire les underscores multiples
    base_name = re.sub(r'_+', '_', base_name)

    # Étape 7: Nettoyer début/fin
    base_name = base_name.strip('_')

    # Reconstituer avec l'extension
    return base_name + extension



class CleanHeaders(TransformComponent):
    """
    Applique la fonction remove_duplicate_headers sur le texte de chaque node.
    """

    def __call__(self, nodes, **kwargs):
        for node in nodes:
            # On modifie le contenu du node en utilisant la méthode prévue à cet effet
            cleaned_text = remove_duplicate_headers(node.get_content())
            node.set_content(cleaned_text)
        return nodes


# src/components.py (VERSION FINALE CORRIGÉE)
import urllib.parse
import requests  # <-- NOUVEL IMPORT
import os  # <-- NOUVEL IMPORT

from llama_index.core.schema import TransformComponent, NodeWithScore, QueryBundle, NodeRelationship, RelatedNodeInfo, \
    TextNode
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from typing import List, Optional
from llama_index.core.storage.docstore.types import BaseDocumentStore
from collections import Counter


# ... [TOUTES VOS CLASSES ET FONCTIONS EXISTANTES RESTENT INCHANGÉES] ...
# FilterEmptyNodes, RepairRelationships, AddBreadcrumbs_bu, AddBreadcrumbs,
# ContextMerger, remove_duplicate_headers, normalize_filename, CleanHeaders
# ...

# ▼▼▼ NOUVELLE CLASSE AJOUTÉE À LA FIN DU FICHIER ▼▼▼

class ApiReranker(BaseNodePostprocessor):
    top_n: int = 5
    model: str
    api_base: str
    api_key: str
    custom_documents: Optional[List[str]] = None  # NEW: Store custom docs

    def _postprocess_nodes(
            self,
            nodes: List[NodeWithScore],
            query_bundle: Optional[QueryBundle] = None,
    ) -> List[NodeWithScore]:
        if query_bundle is None or not nodes:
            print("⚠️ Reranker : Requête ou nodes manquants, étape ignorée.")
            return nodes

        query_str = query_bundle.query_str

        # Use custom_documents if set, otherwise extract from nodes
        if self.custom_documents is not None:
            documents_to_rerank = self.custom_documents
        else:
            documents_to_rerank = [n.node.get_content() for n in nodes]

        rerank_url = f"{self.api_base}/rerank"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": self.model,
            "query": query_str,
            "documents": documents_to_rerank,
            "top_k": self.top_n,
        }

        try:
            print(f"🚀 Envoi de {len(documents_to_rerank)} documents au reranker (modèle: {self.model})...")
            response = requests.post(rerank_url, headers=headers, json=data, timeout=180)
            response.raise_for_status()
            results = response.json()["results"]

            reranked_nodes = []
            for res in results:
                original_index = res.get("index")
                new_score = res.get("relevance_score")

                if original_index is not None and new_score is not None:
                    reranked_node = NodeWithScore(
                        node=nodes[original_index].node,
                        score=new_score
                    )
                    reranked_nodes.append(reranked_node)

            print(f"✅ Reranking réussi. {len(reranked_nodes)} nodes conservés.")
            return reranked_nodes[:self.top_n]

        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur lors de l'appel à l'API de reranking : {e}")
            return nodes[:self.top_n]
        except (KeyError, IndexError) as e:
            print(f"❌ Erreur lors du parsing de la réponse du reranker : {e}")
            return nodes[:self.top_n]

if __name__ == '__main__':
    test = "1.4.0.1_Richtlinie%20%C3%BCber%20das%20Kontinuit%C3%A4tsmanagement%20Bund_f.pdf"
    print(normalize_filename(test))
    # Devrait donner : 1.4.0.1_Richtlinie_uber_das_Kontinuitatsmanagement_Bund_f.pdf