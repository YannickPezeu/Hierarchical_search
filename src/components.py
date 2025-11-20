# src/components.py (VERSION FINALE CORRIGÉE)
import os
import urllib.parse


from dotenv import load_dotenv
load_dotenv()

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple
import re
import unicodedata
import urllib.parse
import urllib.parse
import requests

from llama_index.core.schema import TransformComponent, NodeWithScore, QueryBundle, NodeRelationship, RelatedNodeInfo, \
    TextNode
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.storage.docstore.types import BaseDocumentStore
from collections import Counter

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


class ApiReranker(BaseNodePostprocessor):
    top_n: int = 5
    model: str
    api_base: str
    api_key: str
    custom_documents: Optional[List[str]] = None

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

        # ✅ CORRECTION : Formatter correctement la requête
        data = {
            "model": self.model,
            "query": query_str,
            "documents": documents_to_rerank,
            "top_n": self.top_n,  # ← Attention : certaines APIs utilisent "top_k" au lieu de "top_n"
        }

        try:
            print(f"🚀 Envoi de {len(documents_to_rerank)} documents au reranker (modèle: {self.model})...")

            # ✅ NOUVEAU : Logger la requête pour debug
            logger.debug(f"Rerank request URL: {rerank_url}")
            logger.debug(f"Rerank request headers: {headers}")
            logger.debug(f"Rerank request data keys: {list(data.keys())}")
            logger.debug(f"Query length: {len(query_str)} chars")
            logger.debug(f"Documents count: {len(documents_to_rerank)}")
            logger.debug(f"First document preview: {documents_to_rerank[0][:200]}...")

            response = requests.post(rerank_url, headers=headers, json=data, timeout=180)

            # ✅ NOUVEAU : Logger la réponse en cas d'erreur
            if response.status_code != 200:
                logger.error(f"Reranker API error {response.status_code}")
                logger.error(f"Response: {response.text[:500]}")
                raise requests.exceptions.HTTPError(f"{response.status_code} for {rerank_url}")

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
            logger.error(f"❌ Erreur lors de l'appel à l'API de reranking : {e}")
            # ✅ NOUVEAU : Retourner les nodes originaux au lieu de lever l'exception
            return nodes[:self.top_n]
        except (KeyError, IndexError) as e:
            logger.error(f"❌ Erreur lors du parsing de la réponse du reranker : {e}")
            return nodes[:self.top_n]

import logging
# from typing import List
# from llama_index.core.schema import TextNode, NodeRelationship, RelatedNodeInfo
#
logger = logging.getLogger(__name__)




class MergeSmallNodes(TransformComponent):
    """
    Crée une hiérarchie à deux niveaux :
    1. Fusionne les tiny nodes (< 200 chars) en child nodes (1000-2000 chars)
    2. Fusionne les child nodes en parent nodes (2000-5000 chars)

    Les tiny nodes originaux sont jetés après la fusion.
    """

    # Paramètres pour le premier niveau (tiny -> child)
    tiny_size: int = 200
    child_min_size: int = 1000
    child_max_size: int = 2000

    # Paramètres pour le second niveau (child -> parent)
    parent_min_size: int = 2000
    parent_max_size: int = 5000

    def _group_nodes_by_document(self, nodes):
        """Groupe les nodes par document."""
        docs = {}
        for node in nodes:
            doc_name = node.metadata.get("file_name", "Unknown")
            if doc_name not in docs:
                docs[doc_name] = []
            docs[doc_name].append(node)
        return docs

    def _create_merge_groups(self, nodes_in_doc: List[TextNode], min_size: int, max_size: int, level_name: str = ""):
        """
        Parcourt les nodes d'un document et crée des groupes de fusion.
        """
        merge_groups = []
        current_group = []
        current_group_size = 0

        for node in reversed(nodes_in_doc):
            node_size = len(node.text)

            is_tiny = node_size < self.tiny_size and ("#" in node.text or "image" in node.text.lower())

            if is_tiny and current_group and (current_group_size + node_size > max_size):
                current_group = list(reversed(current_group))
                merge_groups.append(current_group)
                current_group = [node]
                current_group_size = node_size
            elif current_group and (current_group_size + node_size > max_size):
                current_group = list(reversed(current_group))
                merge_groups.append(current_group)
                current_group = [node]
                current_group_size = node_size
            else:
                current_group.append(node)
                current_group_size += node_size

        if current_group:
            current_group = list(reversed(current_group))
            merge_groups.append(current_group)

        return list(reversed(merge_groups))

    def _create_merged_node_from_group(self, source_nodes: List[TextNode]) -> TextNode:
        """Crée un node fusionné à partir d'un groupe de source nodes."""
        if not source_nodes:
            return None

        merged_text = "\n\n".join(node.text for node in source_nodes)

        merged_node = TextNode(
            text=merged_text,
            metadata=source_nodes[0].metadata.copy(),
        )
        return merged_node

    def _first_pass_merge_tiny_to_child(self, original_nodes: List[TextNode]) -> List[TextNode]:
        """
        PREMIÈRE PASSE : Fusionne les tiny nodes en child nodes de taille raisonnable.
        Retourne uniquement les child nodes (les tiny sont jetés).
        """
        print(f"\n{'=' * 80}")
        print(f"PREMIÈRE PASSE : FUSION DES TINY NODES EN CHILD NODES")
        print(f"{'=' * 80}")
        print(f"Paramètres : tiny < {self.tiny_size}, target {self.child_min_size}-{self.child_max_size} chars")

        docs = self._group_nodes_by_document(original_nodes)
        initial_child_nodes = []
        total_groups = 0

        for doc_name, doc_nodes in docs.items():
            print(f"\n--- Document: {doc_name} ({len(doc_nodes)} tiny nodes) ---")

            merge_groups = self._create_merge_groups(doc_nodes, self.child_min_size, self.child_max_size, "child")
            total_groups += len(merge_groups)
            print(f"  • Groupes créés: {len(merge_groups)}")

            for group_idx, group in enumerate(merge_groups):
                child_node = self._create_merged_node_from_group(group)
                initial_child_nodes.append(child_node)
                group_size = len(child_node.text)
                print(f"    Groupe {group_idx + 1}: {len(group)} tiny nodes -> {group_size:,} chars")

        # ✨ NOUVELLE LOGIQUE DE NETTOYAGE (FORCÉE) ✨
        final_child_nodes = []
        for node in initial_child_nodes:
            node_size = len(node.text)

            if node_size < self.tiny_size and final_child_nodes:
                logger.warning(f"  [Nettoyage] Détection d'un child node trop petit ({node_size} chars).")
                logger.warning(f"  [Nettoyage] Contenu : '{node.text}'")

                previous_node = final_child_nodes[-1]

                # La condition de taille a été retirée pour forcer la fusion.
                previous_node.text += "\n\n" + node.text
                new_size = len(previous_node.text)
                logger.warning(
                    f"  [Nettoyage] Fusion forcée avec le node précédent (nouvelle taille: {new_size:,} chars).")
            else:
                final_child_nodes.append(node)

        print(f"\n{'=' * 80}")
        print(f"RÉSULTAT PREMIÈRE PASSE")
        print(f"{'=' * 80}")
        print(f"  • Tiny nodes originaux: {len(original_nodes)} (JETÉS)")
        print(f"  • Child nodes créés: {len(final_child_nodes)} (CONSERVÉS)")
        print(f"  • Total groupes: {total_groups}")

        child_sizes = [len(c.text) for c in final_child_nodes]
        if child_sizes:
            print(f"\nTAILLE DES CHILD NODES:")
            print(f"  • Min: {min(child_sizes):,} chars")
            print(f"  • Max: {max(child_sizes):,} chars")
            print(f"  • Moyenne: {sum(child_sizes) // len(child_sizes):,} chars")

        return final_child_nodes

    def _second_pass_merge_child_to_parent(self, child_nodes: List[TextNode]) -> List[TextNode]:
        """
        SECONDE PASSE : Fusionne les child nodes en parent nodes plus grands.
        """
        print(f"\n{'=' * 80}")
        print(f"SECONDE PASSE : FUSION DES CHILD NODES EN PARENT NODES")
        print(f"{'=' * 80}")
        print(f"Paramètres : target {self.parent_min_size}-{self.parent_max_size} chars")

        docs = self._group_nodes_by_document(child_nodes)
        all_parent_nodes = []
        child_to_parent_mapping = {}
        total_groups = 0

        for doc_name, doc_nodes in docs.items():
            print(f"\n--- Document: {doc_name} ({len(doc_nodes)} child nodes) ---")

            merge_groups = self._create_merge_groups(doc_nodes, self.parent_min_size, self.parent_max_size, "parent")
            total_groups += len(merge_groups)
            print(f"  • Groupes créés: {len(merge_groups)}")

            for group_idx, group in enumerate(merge_groups):
                parent_node = self._create_merged_node_from_group(group)
                all_parent_nodes.append(parent_node)

                for child in group:
                    child_to_parent_mapping[child.id_] = parent_node.id_

                group_size = len(parent_node.text)
                print(f"    Groupe {group_idx + 1}: {len(group)} child nodes -> {group_size:,} chars")

        for child in child_nodes:
            parent_id = child_to_parent_mapping.get(child.id_)
            if parent_id:
                child.relationships[NodeRelationship.PARENT] = RelatedNodeInfo(node_id=parent_id)

        print(f"\n{'=' * 80}")
        print(f"RÉSULTAT SECONDE PASSE")
        print(f"{'=' * 80}")
        print(f"  • Child nodes: {len(child_nodes)}")
        print(f"  • Parent nodes créés: {len(all_parent_nodes)}")
        print(f"  • Total groupes: {total_groups}")

        parent_sizes = [len(p.text) for p in all_parent_nodes]
        if parent_sizes:
            print(f"\nTAILLE DES PARENT NODES:")
            print(f"  • Min: {min(parent_sizes):,} chars")
            print(f"  • Max: {max(parent_sizes):,} chars")
            print(f"  • Moyenne: {sum(parent_sizes) // len(parent_sizes):,} chars")

        return all_parent_nodes

    # À ajouter dans components.py dans la classe MergeSmallNodes

    def _split_at_best_position(self, text: str, target_pos: int) -> Tuple[str, str]:
        """
        Coupe un texte à la position idéale proche de target_pos.
        Priorité : double saut de ligne > point > position exacte
        """
        # Chercher un double saut de ligne dans une fenêtre autour de target_pos
        window = 500  # Chercher dans ±500 chars
        start = max(0, target_pos - window)
        end = min(len(text), target_pos + window)

        # Chercher le dernier double saut de ligne avant target_pos
        search_area = text[start:target_pos]
        double_newline_pos = search_area.rfind('\n\n')

        if double_newline_pos != -1:
            actual_pos = start + double_newline_pos + 2  # +2 pour garder le double \n avec la première partie
            logger.info(f"         ✂️ Split at paragraph break (pos {actual_pos})")
            return text[:actual_pos].rstrip(), text[actual_pos:].lstrip()

        # Sinon chercher un point suivi d'espace/newline
        search_area = text[start:end]
        # Chercher tous les points suivis d'espace ou newline
        import re
        matches = list(re.finditer(r'\.\s', search_area))

        if matches:
            # Prendre le point le plus proche de target_pos
            closest_match = min(matches, key=lambda m: abs((start + m.start()) - target_pos))
            actual_pos = start + closest_match.end()
            logger.info(f"         ✂️ Split at sentence end (pos {actual_pos})")
            return text[:actual_pos].rstrip(), text[actual_pos:].lstrip()

        # Fallback : couper à la position exacte
        logger.warning(f"         ⚠️ No good split point found, cutting at exact position {target_pos}")
        return text[:target_pos], text[target_pos:]

    def _third_pass_split_oversized_nodes(
            self,
            all_nodes: List[TextNode],
            tokenizer,
            max_tokens: int = 8000,
            char_threshold: int = 20000
    ) -> List[TextNode]:
        """
        TROISIÈME PASSE : Split les nodes qui dépassent max_tokens.

        Args:
            all_nodes: Tous les nodes (child + parent)
            tokenizer: Le tokenizer du reranker
            max_tokens: Limite en tokens (8000 pour bge-reranker-v2-m3)
            char_threshold: Ne tokenizer que les nodes > ce seuil (20k chars)
        """
        print(f"\n{'=' * 80}")
        print(f"TROISIÈME PASSE : SPLIT DES NODES TROP GROS")
        print(f"{'=' * 80}")
        print(f"Paramètres : max {max_tokens} tokens, tokenize si > {char_threshold:,} chars")

        result_nodes = []
        split_count = 0
        total_checked = 0

        for node in all_nodes:
            text_length = len(node.text)

            # Ne tokenizer que les gros nodes
            if text_length < char_threshold:
                result_nodes.append(node)
                continue

            # Tokenizer le node
            tokens = tokenizer.encode(node.text, add_special_tokens=False)
            num_tokens = len(tokens)
            total_checked += 1

            logger.info(f"\n   📊 Node {node.id_[:8]}...")
            logger.info(f"      • Caractères : {text_length:,}")
            logger.info(f"      • Tokens : {num_tokens:,}")

            # Si dans la limite, garder tel quel
            if num_tokens <= max_tokens:
                logger.info(f"      ✅ OK (sous la limite)")
                result_nodes.append(node)
                continue

            # Dépasse la limite : split en deux
            logger.warning(f"      ⚠️ DÉPASSE LA LIMITE ! Split en 2...")
            split_count += 1

            # Position cible : milieu du texte (en caractères)
            target_char_pos = text_length // 2

            # Trouver le meilleur endroit pour couper
            first_half, second_half = self._split_at_best_position(node.text, target_char_pos)

            # Créer deux nouveaux nodes
            first_node = TextNode(
                text=first_half,
                metadata=node.metadata.copy(),
            )

            second_node = TextNode(
                text=second_half,
                metadata=node.metadata.copy(),
            )

            # Vérifier les tailles après split
            first_tokens = len(tokenizer.encode(first_half, add_special_tokens=False))
            second_tokens = len(tokenizer.encode(second_half, add_special_tokens=False))

            logger.info(f"         → Part 1 : {len(first_half):,} chars, {first_tokens:,} tokens")
            logger.info(f"         → Part 2 : {len(second_half):,} chars, {second_tokens:,} tokens")

            # Si une des parties dépasse encore (rare), logger un warning
            if first_tokens > max_tokens or second_tokens > max_tokens:
                logger.error(f"         ❌ WARNING : Une partie dépasse encore la limite !")
                logger.error(f"            Ce node nécessiterait plus de 2 splits")

            result_nodes.extend([first_node, second_node])

        print(f"\n{'=' * 80}")
        print(f"RÉSULTAT TROISIÈME PASSE")
        print(f"{'=' * 80}")
        print(f"  • Nodes en entrée : {len(all_nodes)}")
        print(f"  • Nodes > {char_threshold:,} chars vérifiés : {total_checked}")
        print(f"  • Nodes splittés : {split_count}")
        print(f"  • Nodes en sortie : {len(result_nodes)}")
        print(f"{'=' * 80}\n")

        return result_nodes

    def __call__(self, nodes: List[TextNode], **kwargs) -> List[TextNode]:
        if not nodes:
            return nodes

        print("\n" + "=" * 80)
        print("CRÉATION DE LA HIÉRARCHIE À DEUX NIVEAUX")
        print("=" * 80)
        print(f"Nodes initiaux (tiny): {len(nodes)}")

        child_nodes = self._first_pass_merge_tiny_to_child(nodes)
        parent_nodes = self._second_pass_merge_child_to_parent(child_nodes)

        # ✨ NOUVEAU : Charger le tokenizer et split les nodes trop gros
        try:
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-reranker-v2-m3")

            all_nodes_before_split = child_nodes + parent_nodes
            all_nodes_after_split = self._third_pass_split_oversized_nodes(
                all_nodes_before_split,
                tokenizer,
                max_tokens=8000,
                char_threshold=20000
            )

        except Exception as e:
            logger.error(f"❌ Erreur lors du split des nodes oversized : {e}")
            logger.warning("⚠️ Continuing without token-based splitting")
            all_nodes_after_split = child_nodes + parent_nodes

        print(f"\n{'=' * 80}")
        print(f"HIÉRARCHIE FINALE CRÉÉE (AVEC SPLIT OVERSIZED)")
        print(f"{'=' * 80}")
        print(f"  • Nodes finaux : {len(all_nodes_after_split)}")
        print(f"  • (child + parent + splits)")
        print("=" * 80 + "\n")

        return all_nodes_after_split


class FilterTableOfContentsWithLLM(TransformComponent):
    """
    Filtre les tables des matières et contenus inutiles en utilisant un LLM.
    Utilise un préfiltre léger puis fait appel au LLM en parallèle.
    """

    # Seuils de préfiltre
    dot_threshold: float = 0.08
    space_threshold: float = 0.30
    size_threshold: int = 15000
    max_content_length: int = 8000  # Tronquer pour le LLM

    # Paramètres LLM - déclarés comme champs Pydantic
    max_workers: int = 10
    timeout: int = 30
    api_key: str = ""
    api_endpoint: str = ""
    model: str = ""

    def __init__(self, **kwargs):
        # Charger depuis l'environnement si non fourni
        if 'api_key' not in kwargs:
            kwargs['api_key'] = os.getenv("RCP_API_KEY", "")
        if 'api_endpoint' not in kwargs:
            kwargs['api_endpoint'] = os.getenv("RCP_API_ENDPOINT", "")
        if 'model' not in kwargs:
            kwargs['model'] = os.getenv("RCP_MISTRAL_SMALL", "mistralai/Mistral-Small-3.2-24B-Instruct-2506-bfloat16")

        super().__init__(**kwargs)

        if not self.api_key or not self.api_endpoint:
            raise ValueError("RCP_API_KEY et RCP_API_ENDPOINT doivent être définis dans .env")

    def _should_check_with_llm(self, text: str) -> bool:
        """
        Préfiltre : détermine si on doit envoyer le node au LLM.
        Retourne True si au moins un critère est rempli.
        """
        text_lower = text.lower()

        # Critère 1 : Tableau markdown
        has_table = '|' in text

        # Critère 2 : Ratio de points élevé
        dot_ratio = text.count('.') / len(text) if len(text) > 0 else 0
        high_dots = dot_ratio > self.dot_threshold

        # Critère 3 : Ratio d'espaces élevé
        space_ratio = text.count(' ') / len(text) if len(text) > 0 else 0
        high_spaces = space_ratio > self.space_threshold

        # Critère 4 : Taille énorme
        huge_size = len(text) > self.size_threshold

        # Critère 5 : Mots-clés ToC
        toc_keywords = [
            'table des matières', 'table of contents', 'sommaire',
            'inhaltsverzeichnis', 'indice', 'contents',
            'chapitre', 'chapter', 'kapitel'
        ]
        has_toc_keyword = any(kw in text_lower for kw in toc_keywords)

        return has_table or high_dots or high_spaces or huge_size or has_toc_keyword

    def _truncate_content(self, text: str) -> str:
        """Tronque le contenu si trop long pour le LLM."""
        if len(text) <= self.max_content_length:
            return text

        # Garder début + fin
        half = self.max_content_length // 2
        return text[:half] + f"\n\n[... {len(text) - self.max_content_length} chars tronqués ...]\n\n" + text[-half:]

    def _classify_with_llm(self, text: str) -> Dict[str, Any]:
        """
        Appelle le LLM pour classifier si le contenu doit être filtré.
        Retourne: {"should_filter": bool, "reason": str, "error": str ou None}
        """
        truncated_text = self._truncate_content(text)

        prompt = f"""Tu es un assistant qui aide à filtrer du contenu pour un système de recherche documentaire.

TÂCHE : Détermine si le contenu ci-dessous doit être FILTRÉ (supprimé de l'index) ou CONSERVÉ.

FILTRE (supprime) si c'est :
- Une table des matières (liste de chapitres/sections avec numéros de pages)
- Un index ou sommaire sans contenu substantiel
- Une liste de liens/références sans contexte explicatif
- Des métadonnées répétitives sans valeur informative
- Des structures uniquement pour la navigation

CONSERVE si c'est :
- Un tableau de données avec informations utiles (statistiques, comparaisons, etc.)
- Un résumé ou synthèse avec contenu
- Du contenu avec valeur sémantique pour la recherche
- Des listes explicatives avec descriptions
- Du texte normal même s'il contient des tableaux

Réponds UNIQUEMENT avec un JSON valide (pas de markdown, pas de texte avant/après) :
{{"should_filter": true}}
ou
{{"should_filter": false}}

CONTENU À ANALYSER :
{truncated_text}
"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0  # Déterministe
        }

        try:
            response = requests.post(
                f"{self.api_endpoint}/chat/completions",
                headers=headers,
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # Parser le JSON de la réponse
            # Nettoyer les markdown backticks si présents
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            parsed = json.loads(content)

            return {
                "should_filter": parsed.get("should_filter", False),
                "error": None
            }

        except requests.exceptions.Timeout:
            return {"should_filter": False, "error": "Timeout"}
        except requests.exceptions.RequestException as e:
            return {"should_filter": False, "error": f"Request error: {str(e)}"}
        except (json.JSONDecodeError, KeyError) as e:
            return {"should_filter": False, "error": f"Parse error: {str(e)}"}

    def _classify_node(self, node, index: int) -> Dict[str, Any]:
        """Classifie un node individuel."""
        text = node.text
        doc = node.metadata.get("file_name", "Unknown")

        # Préfiltre
        needs_llm_check = self._should_check_with_llm(text)

        if not needs_llm_check:
            return {
                "index": index,
                "node": node,
                "should_filter": False,
                "checked_by_llm": False,
                "doc": doc,
                "size": len(text),
                "error": None
            }

        # Appel LLM
        llm_result = self._classify_with_llm(text)

        return {
            "index": index,
            "node": node,
            "should_filter": llm_result["should_filter"],
            "checked_by_llm": True,
            "doc": doc,
            "size": len(text),
            "error": llm_result["error"]
        }

    def __call__(self, nodes, **kwargs):
        if not nodes:
            return nodes

        print(f"\n{'=' * 80}")
        print(f"FILTRAGE DES TABLES DES MATIERES AVEC LLM")
        print(f"{'=' * 80}")
        print(f"Noeuds en entree: {len(nodes)}")
        print(f"Modele LLM: {self.model}")
        print(f"Workers paralleles: {self.max_workers}")

        # Parallélisation des classifications
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._classify_node, node, i): i
                for i, node in enumerate(nodes)
            }

            completed = 0
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                completed += 1

                if completed % 50 == 0:
                    print(f"  Progression: {completed}/{len(nodes)} noeuds traites...")

        # Trier par index pour garder l'ordre
        results.sort(key=lambda x: x["index"])

        # Séparer noeuds filtrés et conservés
        filtered_nodes = []
        kept_nodes = []

        for result in results:
            if result["should_filter"]:
                filtered_nodes.append(result)
            else:
                kept_nodes.append(result["node"])

        # Statistiques
        prefilter_passed = sum(1 for r in results if not r["checked_by_llm"])
        llm_checked = sum(1 for r in results if r["checked_by_llm"])
        llm_filtered = sum(1 for r in results if r["checked_by_llm"] and r["should_filter"])
        llm_kept = sum(1 for r in results if r["checked_by_llm"] and not r["should_filter"])
        errors = sum(1 for r in results if r["error"])

        print(f"\n{'=' * 80}")
        print(f"STATISTIQUES DU FILTRAGE")
        print(f"{'=' * 80}")
        print(f"  Total noeuds: {len(nodes)}")
        print(f"  Prefiltre OK (gardes direct): {prefilter_passed}")
        print(f"  Envoyes au LLM: {llm_checked}")
        print(f"    - Filtres par LLM: {llm_filtered}")
        print(f"    - Conserves par LLM: {llm_kept}")
        print(f"  Erreurs LLM (gardes par precaution): {errors}")
        print(f"  TOTAL CONSERVE: {len(kept_nodes)}")
        print(f"  TOTAL FILTRE: {len(filtered_nodes)}")

        # Log détaillé des nodes filtrés
        if filtered_nodes:
            print(f"\n{'=' * 80}")
            print(f"NOEUDS FILTRES PAR LE LLM ({len(filtered_nodes)})")
            print(f"{'=' * 80}")

            for result in filtered_nodes:
                print(f"\n{'-' * 80}")
                print(f"[Filtre - Noeud #{result['index']}]")
                print(f"  Document: {result['doc']}")
                print(f"  Taille: {result['size']:,} chars")

                # Aperçu
                preview_lines = result["node"].text.split('\n')[:10]
                print(f"  Apercu:")
                for line in preview_lines:
                    if line.strip():
                        print(f"    {line[:100]}")

        # Log détaillé des checks LLM (conservés)
        llm_kept_results = [r for r in results if r["checked_by_llm"] and not r["should_filter"]]
        if llm_kept_results:
            print(f"\n{'=' * 80}")
            print(f"NOEUDS VERIFIES PAR LLM ET CONSERVES ({len(llm_kept_results)})")
            print(f"{'=' * 80}")

            for result in llm_kept_results[:20]:  # Limiter à 20 pour pas trop de logs
                print(f"\n[Conserve - Noeud #{result['index']}]")
                print(f"  Document: {result['doc']}")
                print(f"  Taille: {result['size']:,} chars")

                if result['error']:
                    print(f"  Erreur: {result['error']}")

            if len(llm_kept_results) > 20:
                print(f"\n  ... et {len(llm_kept_results) - 20} autres noeuds conserves")

        # Log des erreurs
        error_results = [r for r in results if r["error"]]
        if error_results:
            print(f"\n{'=' * 80}")
            print(f"ERREURS LLM ({len(error_results)} noeuds)")
            print(f"{'=' * 80}")
            for result in error_results:
                print(f"  Noeud #{result['index']} ({result['doc']}): {result['error']}")

        print(f"\n{'=' * 80}")
        print(f"FILTRAGE TERMINE")
        print(f"{'=' * 80}\n")

        return kept_nodes

if __name__ == '__main__':
    test = "1.4.0.1_Richtlinie%20%C3%BCber%20das%20Kontinuit%C3%A4tsmanagement%20Bund_f.pdf"
    print(normalize_filename(test))
    # Devrait donner : 1.4.0.1_Richtlinie_uber_das_Kontinuitatsmanagement_Bund_f.pdf