# src/components.py (VERSION FINALE CORRIGÉE)
import urllib.parse

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
class AddBreadcrumbs(BaseNodePostprocessor):
    def _postprocess_nodes(self, nodes: List[NodeWithScore], query_bundle: Optional[QueryBundle] = None) -> List[NodeWithScore]:
        for n in nodes:
            header_keys = sorted([key for key in n.node.metadata.keys() if key.startswith("Header")])
            if header_keys:
                breadcrumbs = " > ".join([n.node.metadata[key] for key in header_keys])
                file_name = n.node.metadata.get("file_name", "Document")
                n.node.set_content(f"Source: {file_name}\nContexte: {breadcrumbs}\n---\n{n.node.get_content()}")
        return nodes
    

class ContextMerger(BaseNodePostprocessor):
    """
    Fusionne chaque node avec ses voisins (précédent et suivant) 
    pour créer un seul node de contexte étendu.
    """
    docstore: BaseDocumentStore

    def _postprocess_nodes(self, nodes: List[NodeWithScore], query_bundle: Optional[QueryBundle] = None) -> List[NodeWithScore]:
        if not nodes:
            return []

        docstore = self.docstore
        merged_nodes = []

        for node_with_score in nodes:
            original_node = node_with_score.node
            
            # Récupérer les textes des voisins
            prev_text = docstore.get_node(original_node.prev_node.node_id).get_content() if original_node.prev_node else ""
            next_text = docstore.get_node(original_node.next_node.node_id).get_content() if original_node.next_node else ""
            
            # Concaténer les textes
            merged_text = f"{prev_text}\n\n---\n\n{original_node.get_content()}\n\n---\n\n{next_text}".strip()
            
            # Créer un nouveau node fusionné
            merged_node = NodeWithScore(
                node=TextNode(
                    text=merged_text,
                    metadata=original_node.metadata # On garde les métadonnées du node central
                ),
                score=node_with_score.score # On garde le score du node central
            )
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


def normalize_filename(filename: str) -> str:
    """
    Normalise un nom de fichier de manière universelle :
    1. Décode les caractères d'URL (ex: %20 -> espace).
    2. Remplace les différents types d'apostrophes par un underscore.
    """
    # Étape 1: Décoder les caractères d'URL
    name = urllib.parse.unquote(filename)

    # Étape 2: Remplacer les apostrophes (notre logique précédente)
    name = name.replace("’", "_")
    name = name.replace("'", "_")

    return name

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