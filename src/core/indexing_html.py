# src/core/indexing_html.py - VERSION HIÉRARCHIQUE
import os

from src.core.utils import _normalize_text_for_comparison
from bs4 import BeautifulSoup, NavigableString
import logging
import re
from rapidfuzz import fuzz
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def _merge_small_anchors(anchors: List[Dict]) -> List[Dict]:
    """
    Fusionne les ancres trop petites avec leurs voisines.
    Similaire à MergeSmallNodes.

    Règles:
    - Ancres < 500 chars : fusionner avec la suivante
    - Ancres >= 500 chars : conserver
    - Maximum après fusion : 5000 chars
    """
    if not anchors:
        return []

    MIN_SIZE = 500
    MAX_SIZE = 5000

    merged = []
    i = 0

    while i < len(anchors):
        current = anchors[i]

        # Si l'ancre est assez grande, la garder telle quelle
        if current['scope_length'] >= MIN_SIZE:
            merged.append(current)
            i += 1
            continue

        # Sinon, essayer de fusionner avec les suivantes
        merged_scope = current['scope']
        merged_ids = [current['id']]
        merged_length = current['scope_length']
        j = i + 1

        # Fusionner avec les ancres suivantes jusqu'à atteindre MIN_SIZE ou MAX_SIZE
        while j < len(anchors) and merged_length < MIN_SIZE:
            next_anchor = anchors[j]

            # Vérifier qu'on ne dépasse pas MAX_SIZE
            if merged_length + next_anchor['scope_length'] > MAX_SIZE:
                break

            merged_scope += ' ' + next_anchor['scope']
            merged_ids.append(next_anchor['id'])
            merged_length += next_anchor['scope_length']
            j += 1

        # Créer l'ancre fusionnée
        merged_anchor = {
            'id': merged_ids[0],  # Utiliser l'ID du premier header
            'tag': current['tag'],
            'level': current['level'],
            'header_text': current['header_text'],
            'scope': merged_scope,
            'scope_length': merged_length,
            'has_native_id': current['has_native_id'],
            'merged_from': merged_ids if len(merged_ids) > 1 else None
        }

        merged.append(merged_anchor)
        i = j

    return merged


def _slugify(text: str) -> str:
    """Crée un slug à partir d'un texte."""
    import re
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:50]  # Limiter la longueur


def _is_in_collapsible(element) -> bool:
    """
    Vérifie si un élément est à l'intérieur d'un collapsible/accordéon fermé.
    Détecte les patterns courants : collapse Bootstrap, details/summary, aria-hidden, etc.
    """
    current = element.parent

    while current:
        # Pattern 1 : Bootstrap collapse avec aria-expanded="false"
        if current.name in ['div', 'section']:
            # Chercher un bouton/lien de contrôle dans les siblings/parents
            collapse_id = current.get('id')
            if collapse_id:
                # Chercher un bouton avec data-target ou aria-controls pointant vers cet ID
                root = element.find_parent(['body', 'html']) or element
                controls = root.find_all(['button', 'a'], attrs={
                    'data-toggle': 'collapse'
                })

                for control in controls:
                    target = control.get('data-target', '').lstrip('#')
                    aria_controls = control.get('aria-controls', '').lstrip('#')

                    if target == collapse_id or aria_controls == collapse_id:
                        # Vérifier si le collapse est fermé
                        if control.get('aria-expanded') == 'false':
                            return True
                        # Vérifier si le div collapse a la classe 'show'
                        if 'show' not in current.get('class', []):
                            return True

        # Pattern 2 : <details> sans attribut open
        if current.name == 'details' and not current.has_attr('open'):
            return True

        # Pattern 3 : aria-hidden="true"
        if current.get('aria-hidden') == 'true':
            return True

        # Pattern 4 : Classes communes pour contenu caché
        classes = current.get('class', [])
        hidden_classes = ['collapse', 'hidden', 'd-none', 'hide', 'invisible']
        if any(cls in classes for cls in hidden_classes):
            # Vérifier si le collapse est ouvert (classe 'show')
            if 'collapse' in classes and 'show' not in classes:
                return True
            elif any(cls in ['hidden', 'd-none', 'hide', 'invisible'] for cls in classes):
                return True

        current = current.parent

    return False


def _find_collapsible_title(element) -> Optional[str]:
    """
    Si un élément est dans un collapsible, trouve le titre/bouton qui contrôle ce collapsible.
    Retourne le texte du bouton de contrôle.
    """
    current = element.parent

    while current:
        if current.name in ['div', 'section']:
            collapse_id = current.get('id')
            if collapse_id:
                # Chercher le bouton de contrôle
                root = element.find_parent(['body', 'html']) or element
                controls = root.find_all(['button', 'a'], attrs={
                    'data-toggle': 'collapse'
                })

                for control in controls:
                    target = control.get('data-target', '').lstrip('#')
                    aria_controls = control.get('aria-controls', '').lstrip('#')

                    if target == collapse_id or aria_controls == collapse_id:
                        # Extraire le texte du bouton
                        title_text = control.get_text(separator=' ', strip=True)
                        if title_text:
                            return title_text

        # Pour <details>, chercher le <summary>
        if current.name == 'details':
            summary = current.find('summary')
            if summary:
                return summary.get_text(separator=' ', strip=True)

        current = current.parent

    return None


def _normalize_punctuation_spacing(text: str) -> str:
    """
    Normalise les espaces UNIQUEMENT avant les virgules et les points.
    Laisse les espaces avant : ! ? ; (pour le français)
    """
    # Supprimer les espaces avant , et .
    text = re.sub(r'\s+([,.])', r'\1', text)
    # Supprimer les espaces multiples
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _is_clean_text(text: str) -> bool:
    """
    Vérifie si un texte ne contient que des caractères "safe" pour les text fragments.
    Accepte : lettres, chiffres, espaces, ponctuation de base
    Rejette : flèches, puces spéciales, symboles unicode complexes, etc.
    """
    # Caractères acceptés : alphanumériques + ponctuation de base + accents français
    # ✅ Ajout des apostrophes typographiques : \u2018 \u2019 (courbes gauche et droite)
    safe_pattern = r'^[a-zA-Z0-9àâäéèêëïîôùûüÿæœçÀÂÄÉÈÊËÏÎÔÙÛÜŸÆŒÇ\s.,;:!?\'"()\-\u2018\u2019]+$'
    return bool(re.match(safe_pattern, text))


def _has_punctuation(word: str) -> bool:
    """Vérifie si un mot contient de la ponctuation."""
    return bool(re.search(r'[.,;:!?\'"()\-]', word))


def _extract_start_end_fragments(text: str, window_size: int = 5) -> Tuple[Optional[str], Optional[str]]:
    """
    Extrait un fragment de début et de fin depuis un texte, en cherchant des fenêtres
    de mots sans ponctuation.

    Args:
        text: Le texte à analyser
        window_size: Taille de la fenêtre (nombre de mots consécutifs sans ponctuation)

    Returns:
        Tuple (start_fragment, end_fragment) ou (None, None) si impossible
        Si les fragments se chevauchent, retourne (same_fragment, same_fragment)
    """
    # Normaliser d'abord la ponctuation
    text = _normalize_punctuation_spacing(text)

    # Découper en mots
    words = text.split()

    if len(words) < window_size:
        # Texte trop court, retourner tel quel si pas de ponctuation
        if not any(_has_punctuation(w) for w in words):
            full_text = ' '.join(words)
            return (full_text, full_text)
        return (None, None)

    # ✅ Si le texte est court (< 15 mots), utiliser un seul fragment
    if len(words) < 15:
        # Essayer d'extraire une fenêtre sans ponctuation
        for i in range(len(words) - window_size + 1):
            window = words[i:i + window_size]
            if not any(_has_punctuation(w) for w in window):
                fragment = ' '.join(window)
                return (fragment, fragment)

        # Si pas de fenêtre clean, utiliser tout le texte s'il est propre
        if not any(_has_punctuation(w) for w in words):
            full_text = ' '.join(words)
            return (full_text, full_text)

        return (None, None)

    start_fragment = None
    end_fragment = None
    start_index = -1
    end_index = -1

    # Chercher la PREMIÈRE fenêtre de 5 mots sans ponctuation (START)
    for i in range(len(words) - window_size + 1):
        window = words[i:i + window_size]

        # Vérifier si aucun mot de la fenêtre n'a de ponctuation
        if not any(_has_punctuation(w) for w in window):
            start_fragment = ' '.join(window)
            start_index = i
            break

    # Chercher la DERNIÈRE fenêtre de 5 mots sans ponctuation (END)
    for i in range(len(words) - window_size, -1, -1):
        window = words[i:i + window_size]

        # Vérifier si aucun mot de la fenêtre n'a de ponctuation
        if not any(_has_punctuation(w) for w in window):
            end_fragment = ' '.join(window)
            end_index = i
            break

    # ✅ VÉRIFIER LE CHEVAUCHEMENT
    if start_fragment and end_fragment and start_index >= 0 and end_index >= 0:
        # Les fenêtres se chevauchent si : start_index + window_size > end_index
        if start_index + window_size > end_index:
            # Chevauchement détecté ! Utiliser un seul fragment
            # Prendre le plus long des deux, ou le texte complet s'il est propre
            logger.debug(f"         ⚠️ Fragment overlap detected, using single fragment")

            # Essayer d'utiliser tout le texte entre start et end s'il est propre
            full_span = ' '.join(words[start_index:end_index + window_size])
            if _is_clean_text(full_span) and len(full_span) < 200:
                return (full_span, full_span)

            # Sinon, utiliser le fragment de début
            return (start_fragment, start_fragment)

    # Si on n'a trouvé ni start ni end, essayer avec une fenêtre plus petite
    if not start_fragment and not end_fragment and window_size > 2:
        return _extract_start_end_fragments(text, window_size - 1)

    return (start_fragment, end_fragment)


def _extract_longest_clean_substring(text: str, min_length: int = 20) -> str | None:
    """
    Extrait le plus long sous-texte "clean" d'un texte.
    Découpe par phrases/segments et trouve la plus longue séquence propre.
    """
    # Découper par phrases (., !, ?, \n)
    segments = re.split(r'[.!?\n]+', text)

    longest_clean = None
    max_length = 0

    for segment in segments:
        segment = segment.strip()

        if len(segment) < min_length:
            continue

        if _is_clean_text(segment):
            if len(segment) > max_length:
                longest_clean = segment
                max_length = len(segment)

    # Si aucun segment complet n'est clean, essayer de nettoyer le plus long segment
    if not longest_clean and segments:
        # Prendre le plus long segment
        longest_segment = max(segments, key=len).strip()

        # Essayer d'extraire une sous-partie clean
        words = longest_segment.split()
        clean_words = []
        best_sequence = None
        best_sequence_length = 0

        for word in words:
            if _is_clean_text(word):
                clean_words.append(word)
            else:
                # Dès qu'on trouve un mot "sale", sauvegarder la séquence si elle est bonne
                current_sequence = ' '.join(clean_words)
                if len(current_sequence) > best_sequence_length:
                    best_sequence = current_sequence
                    best_sequence_length = len(current_sequence)
                # Reset et continuer
                clean_words = []

        # Vérifier la dernière séquence aussi
        current_sequence = ' '.join(clean_words)
        if len(current_sequence) > best_sequence_length:
            best_sequence = current_sequence
            best_sequence_length = len(current_sequence)

        # Retourner la meilleure séquence si elle est assez longue
        if best_sequence and best_sequence_length >= min_length:
            return _normalize_punctuation_spacing(best_sequence)

    if longest_clean:
        return _normalize_punctuation_spacing(longest_clean)

    return None


def _find_best_paragraph_for_node(
        node_normalized: str,
        all_text_elements: List,
        threshold: int = 90
) -> tuple[Optional[Tuple[str, str]], List[Dict]]:
    """
    Trouve le meilleur élément de texte (p, h1-h6) pour un node donné avec fuzzy matching.
    Privilégie les textes sans caractères spéciaux ET visibles (pas dans un collapse fermé).

    Returns:
        Tuple ((start_fragment, end_fragment), all_candidates)
        Les fragments sont utilisés pour construire #:~:text=start,end
    """
    all_candidates = []

    for element in all_text_elements:
        # Extraire le texte brut (non normalisé) pour le retour final
        element_text_raw = element.get_text(separator=' ', strip=True)

        # Identifier le type d'élément
        element_type = element.name

        # Skip les éléments vides ou trop courts
        if len(element_text_raw) < 30:
            continue

        # Normaliser pour la comparaison
        element_text_normalized = _normalize_text_for_comparison(element_text_raw)

        # Skip si le texte normalisé est trop court
        if len(element_text_normalized) < 20:
            continue

        # ✨ Fuzzy matching pour voir si l'élément est contenu dans le node
        score = fuzz.partial_ratio(element_text_normalized, node_normalized)

        # ✅ Vérifier si le texte est "clean" (sans caractères spéciaux)
        is_clean = _is_clean_text(element_text_raw)

        # ✅ NOUVEAU : Vérifier si le texte est visible (pas dans un collapse fermé)
        is_visible = not _is_in_collapsible(element)

        all_candidates.append({
            'raw': element_text_raw,
            'normalized': element_text_normalized,
            'length': len(element_text_raw),
            'score': score,
            'meets_threshold': score >= threshold,
            'type': element_type,
            'is_clean': is_clean,
            'is_visible': is_visible,
            'element': element
        })

    # Trier par : 1) visible d'abord, 2) cleanness, 3) score décroissant, 4) longueur
    all_candidates.sort(key=lambda x: (not x['is_visible'], not x['is_clean'], -x['score'], -x['length']))

    # ✅ STRATÉGIE 1 : Chercher un élément clean ET visible qui dépasse le seuil
    clean_visible_matching = [c for c in all_candidates if c['meets_threshold'] and c['is_clean'] and c['is_visible']]

    if clean_visible_matching:
        best = clean_visible_matching[0]
        # ✅ Extraire les fragments start/end
        start_fragment, end_fragment = _extract_start_end_fragments(best['raw'])

        if start_fragment and end_fragment:
            logger.info(f"      ✅ Clean & visible text found with fragments:")
            logger.info(f"         Start: '{start_fragment}'")
            logger.info(f"         End: '{end_fragment}'")
            return (start_fragment, end_fragment), all_candidates

    # ✅ STRATÉGIE 2 : Si pas de texte clean visible, chercher juste un texte visible
    visible_matching = [c for c in all_candidates if c['meets_threshold'] and c['is_visible']]

    if visible_matching:
        best = visible_matching[0]

        # Essayer d'extraire un sous-texte clean
        clean_substring = _extract_longest_clean_substring(best['raw'])

        if clean_substring:
            # Extraire les fragments du sous-texte clean
            start_fragment, end_fragment = _extract_start_end_fragments(clean_substring)

            if start_fragment and end_fragment:
                logger.info(f"      ⚠️ Visible text found, extracted clean substring with fragments:")
                logger.info(f"         Start: '{start_fragment}'")
                logger.info(f"         End: '{end_fragment}'")
                return (start_fragment, end_fragment), all_candidates

    # ✅ STRATÉGIE 3 : Tous les bons matches sont dans des collapsibles fermés
    # → Chercher le titre du collapsible parent
    hidden_matching = [c for c in all_candidates if c['meets_threshold'] and not c['is_visible']]

    if hidden_matching:
        best_hidden = hidden_matching[0]
        collapsible_title = _find_collapsible_title(best_hidden['element'])

        if collapsible_title:
            logger.warning(f"      ⚠️ Best match is hidden in collapsible")
            logger.warning(f"         Using collapsible title instead: '{collapsible_title}'")

            # Vérifier si le titre est assez propre pour des fragments
            if _is_clean_text(collapsible_title):
                start_fragment, end_fragment = _extract_start_end_fragments(collapsible_title)

                if start_fragment and end_fragment:
                    logger.info(f"         Title fragments:")
                    logger.info(f"         Start: '{start_fragment}'")
                    logger.info(f"         End: '{end_fragment}'")
                    return (start_fragment, end_fragment), all_candidates

            # Sinon, utiliser le titre complet comme fragment simple
            normalized_title = _normalize_punctuation_spacing(collapsible_title)
            logger.info(f"         Using full title as single fragment: '{normalized_title}'")
            return (normalized_title, normalized_title), all_candidates

    # ✅ STRATÉGIE 4 : Aucun match utilisable trouvé
    logger.warning(f"      ⚠️ Could not extract usable fragments")
    return None, all_candidates


def _annotate_html_with_anchors(nodes: List, html_path: str) -> int:
    """
    Annote les child nodes avec les meilleurs fragments start/end pour text-fragment.

    ⚠️ VERSION HIÉRARCHIQUE : Le html_path est déjà le chemin complet correct
    (construit avec la hiérarchie dans indexing.py)
    """
    try:
        # ✅ Le chemin est déjà correct grâce à la structure hiérarchique
        logger.info(f"   🌐 Processing HTML: {os.path.basename(html_path)}")

        with open(html_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')

        logger.info(f"   🌐 HTML chargé pour extraction des éléments de texte")

        # ✨ Extraire tous les éléments de texte pertinents (paragraphes ET headers)
        all_text_elements = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])

        # Compter par type
        element_counts = {}
        for elem in all_text_elements:
            element_counts[elem.name] = element_counts.get(elem.name, 0) + 1

        logger.info(f"   📊 {len(all_text_elements)} éléments de texte trouvés:")
        for elem_type, count in sorted(element_counts.items()):
            logger.info(f"      • {elem_type}: {count}")

        if not all_text_elements:
            logger.warning(f"   ⚠️ Aucun élément de texte trouvé dans le HTML")
            for node in nodes:
                node.metadata['search_text_start'] = None
                node.metadata['search_text_end'] = None
                node.metadata['anchor_type'] = 'no_text_elements'
            return 0

        annotated_count = 0
        fallback_count = 0

        for idx, node in enumerate(nodes):
            logger.info(f"\n   📄 Node {idx + 1}/{len(nodes)} (ID: {node.id_[:8]}..., {len(node.text):,} chars)")

            # Normaliser le texte du node pour comparaison
            node_normalized = _normalize_text_for_comparison(node.text)

            if len(node_normalized) < 50:
                logger.warning(f"      ⚠️ Node trop court ({len(node_normalized)} chars), skipping")
                node.metadata['search_text_start'] = None
                node.metadata['search_text_end'] = None
                node.metadata['anchor_type'] = 'too_short'
                fallback_count += 1
                continue

            # Trouver les meilleurs fragments avec infos de debug
            fragments, all_candidates = _find_best_paragraph_for_node(
                node_normalized,
                all_text_elements,
                threshold=90
            )

            if fragments and fragments[0] and fragments[1]:
                start_fragment, end_fragment = fragments

                logger.info(f"      ✅ Fragments trouvés:")
                logger.info(f"         Start ({len(start_fragment)} chars): '{start_fragment}'")
                logger.info(f"         End ({len(end_fragment)} chars): '{end_fragment}'")

                node.metadata['search_text_start'] = start_fragment
                node.metadata['search_text_end'] = end_fragment
                node.metadata['anchor_type'] = 'text_fragment'
                annotated_count += 1
            else:
                # ✨ LOGS DÉTAILLÉS EN CAS D'ÉCHEC
                logger.warning(f"      ⚠️ Aucun fragment satisfaisant trouvé")
                logger.warning("=" * 100)
                logger.warning("      >>> DIAGNOSTIC: ÉCHEC DE MATCHING <<<")
                logger.warning("=" * 100)

                # Afficher le texte complet du node
                logger.warning(f"\n      [TEXTE COMPLET DU NODE - ORIGINAL] ({len(node.text):,} chars):")
                logger.warning("-" * 100)
                logger.warning(node.text[:500])
                logger.warning("-" * 100)

                logger.warning(f"\n      [TEXTE COMPLET DU NODE - NORMALISÉ] ({len(node_normalized):,} chars):")
                logger.warning("-" * 100)
                logger.warning(node_normalized[:500])
                logger.warning("-" * 100)

                # Afficher les 5 meilleurs candidats
                top_candidates = all_candidates[:5]
                logger.warning(f"\n      [TOP 5 ÉLÉMENTS ANALYSÉS]")
                logger.warning("=" * 100)

                for i, candidate in enumerate(top_candidates, 1):
                    logger.warning(f"\n      ÉLÉMENT #{i} (<{candidate['type']}>):")
                    logger.warning(f"         Score: {candidate['score']}%")
                    logger.warning(f"         Longueur: {candidate['length']} chars")
                    logger.warning(f"         Clean: {'✅ OUI' if candidate['is_clean'] else '❌ NON'}")
                    logger.warning(
                        f"         Visible: {'✅ OUI' if candidate['is_visible'] else '❌ NON (dans collapse fermé)'}")
                    logger.warning(
                        f"         Dépasse le seuil (90%): {'✅ OUI' if candidate['meets_threshold'] else '❌ NON'}")
                    logger.warning("")
                    logger.warning(f"         [TEXTE ORIGINAL]:")
                    logger.warning("-" * 100)
                    logger.warning(candidate['raw'][:200])
                    logger.warning("-" * 100)

                if not all_candidates:
                    logger.warning("\n      ⚠️ Aucun élément n'a été analysé (tous < 30 chars)")
                elif len(all_candidates) > 5:
                    logger.warning(
                        f"\n      ... et {len(all_candidates) - 5} autres éléments avec des scores inférieurs")

                logger.warning("=" * 100)

                node.metadata['search_text_start'] = None
                node.metadata['search_text_end'] = None
                node.metadata['anchor_type'] = 'no_match'
                fallback_count += 1

        logger.info(f"\n{'=' * 80}")
        logger.info(f"RÉSULTAT ANNOTATION HTML (TEXT-FRAGMENTS)")
        logger.info(f"{'=' * 80}")
        logger.info(f"  ✅ Nodes avec fragments: {annotated_count}")
        logger.info(f"  ⚠️ Nodes sans fragments: {fallback_count}")
        logger.info(f"  📊 Taux de succès: {annotated_count / len(nodes) * 100:.1f}%")
        logger.info(f"{'=' * 80}\n")

        return annotated_count

    except Exception as e:
        logger.error(f"   ❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
        return 0


def _extract_header_scope(header, all_headers: List, current_index: int) -> str:
    """
    Extrait tout le contenu entre ce header et le prochain header de même niveau ou supérieur.

    Si le header n'a pas de siblings (ex: isolé dans un <header> ou <div>),
    on remonte au parent et on prend ses siblings.
    """
    scope_texts = []

    # Texte du header lui-même
    header_text = header.get_text(separator=' ', strip=True)
    scope_texts.append(header_text)

    # Niveau du header actuel
    current_level = int(header.name[1])

    # Trouver le prochain header de même niveau ou supérieur
    next_header = None
    for i in range(current_index + 1, len(all_headers)):
        next_level = int(all_headers[i].name[1])
        if next_level <= current_level:
            next_header = all_headers[i]
            break

    # ✨ NOUVEAU : Trouver l'élément de départ pour les siblings
    # Si le header n'a pas de siblings, remonter au parent
    start_element = header
    max_attempts = 3  # Remonter max 3 niveaux

    for attempt in range(max_attempts):
        siblings = list(start_element.find_next_siblings())

        # Filtrer les siblings vides/inutiles
        valid_siblings = [s for s in siblings if s.name not in ['script', 'style', 'noscript']]

        if valid_siblings:
            logger.debug(f"         Found {len(valid_siblings)} siblings at level {attempt}")
            break

        # Pas de siblings, remonter au parent
        if start_element.parent and start_element.parent.name not in ['html', 'body', '[document]']:
            logger.debug(f"         No siblings, going up to parent: {start_element.parent.name}")
            start_element = start_element.parent
        else:
            break

    # Collecter tous les siblings entre ce header et le prochain
    for sibling in start_element.find_next_siblings():
        # Arrêter si on atteint le prochain header
        if next_header and sibling == next_header:
            break

        # Arrêter si on trouve le prochain header dans les descendants du sibling
        if next_header and next_header in sibling.descendants:
            # Prendre le contenu jusqu'au next_header
            sibling_text = _extract_text_until_element(sibling, next_header)
            if sibling_text:
                scope_texts.append(sibling_text)
            break

        # Ignorer scripts/styles
        if sibling.name in ['script', 'style', 'noscript']:
            continue

        # Ajouter le texte complet (avec descendants)
        sibling_text = sibling.get_text(separator=' ', strip=True)
        if sibling_text:
            scope_texts.append(sibling_text)

    full_scope = ' '.join(scope_texts)
    logger.debug(f"         Scope extracted: {len(full_scope)} chars")

    return full_scope


def _extract_text_until_element(container, stop_element) -> str:
    """
    Extrait le texte d'un conteneur jusqu'à un élément spécifique (exclus).
    """
    texts = []

    for element in container.descendants:
        # Arrêter si on atteint l'élément stop
        if element == stop_element:
            break

        # Prendre seulement les textes (NavigableString)
        if isinstance(element, NavigableString):
            text = str(element).strip()
            if text:
                texts.append(text)

    return ' '.join(texts)


def clean_html_before_docling(html_path: str) -> str:
    """
    Nettoie un fichier HTML en retirant tous les éléments non pertinents
    AVANT la conversion Docling.

    Crée un fichier temporaire nettoyé et retourne son chemin.

    Args:
        html_path: Chemin vers le fichier HTML original (peut contenir une hiérarchie)

    Returns:
        Chemin vers le fichier HTML nettoyé (temporaire)

    ⚠️ VERSION HIÉRARCHIQUE : Le html_path est déjà le chemin complet correct
    """
    from bs4 import BeautifulSoup
    import tempfile
    import os

    logger.info(f"🧹 Nettoyage du HTML avant Docling...")
    logger.info(f"   Source: {html_path}")

    # Charger le HTML
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    # 1️⃣ Classes à retirer (navigation, menus, sidebars, etc.)
    classes_to_remove = [
        # Navigation
        'nav-aside-wrapper',
        'nav-aside',
        'nav-container',
        'nav-menu',
        'navigation',
        'navbar',

        # Menus
        'menu',
        'menu-item',
        'sub-menu',
        'menu-wrapper',

        # Breadcrumbs
        'breadcrumb',
        'breadcrumb-container',
        'breadcrumbs',

        # Footer
        'footer',
        'site-footer',
        'page-footer',

        # Sidebar
        'sidebar',
        'aside',
        'widget',

        # Utilitaires (cachés, accessibilité)
        'sr-only',
        'sr-only-xl',
        'screen-reader-text',
        'hidden',
        'visually-hidden',

        # Partage social
        'social',
        'share',
        'social-share',

        # Commentaires
        'comments',
        'comment-form',

        # Pub
        'ad',
        'advertisement',
        'banner',
    ]

    # 2️⃣ Tags à retirer
    tags_to_remove = [
        'nav',
        'footer',
        'aside',
        'script',
        'style',
        'noscript',
        'iframe',
    ]

    # 3️⃣ IDs à retirer
    ids_to_remove = [
        'nav-aside',
        'menu-main',
        'sidebar',
        'footer',
        'comments',
    ]

    removed_count = 0

    # Retirer par classe
    for class_name in classes_to_remove:
        elements = soup.find_all(class_=class_name)
        for element in elements:
            element.decompose()
            removed_count += 1

    # Retirer par tag
    for tag_name in tags_to_remove:
        elements = soup.find_all(tag_name)
        for element in elements:
            element.decompose()
            removed_count += 1

    # Retirer par ID
    for id_name in ids_to_remove:
        element = soup.find(id=id_name)
        if element:
            element.decompose()
            removed_count += 1

    logger.info(f"   ✂️ {removed_count} éléments retirés")

    # ✨ 4️⃣ NOUVEAU : Nettoyer les liens (garder le texte, retirer l'URL)
    links_cleaned = 0
    for link in soup.find_all('a'):
        # Garder seulement le texte du lien, supprimer l'URL
        link_text = link.get_text(strip=True)
        if link_text:
            # Remplacer le tag <a> par son texte
            link.replace_with(link_text)
            links_cleaned += 1
        else:
            # Si le lien n'a pas de texte, le supprimer complètement
            link.decompose()

    logger.info(f"   🔗 {links_cleaned} liens nettoyés (URLs retirées, texte conservé)")

    # Créer un fichier temporaire avec le HTML nettoyé
    temp_fd, temp_path = tempfile.mkstemp(suffix='.html', prefix='cleaned_')

    try:
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
            f.write(str(soup))

        logger.info(f"   💾 HTML nettoyé sauvegardé: {os.path.basename(temp_path)}")
        return temp_path

    except Exception as e:
        logger.error(f"   ❌ Erreur lors de la sauvegarde du HTML nettoyé: {e}")
        os.close(temp_fd)
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def _extract_all_headers_as_anchors(soup) -> List[Dict]:
    """
    Trouve tous les headers h1-h4 et crée une "ancre" pour chacun.
    ✨ Garde maintenant la référence à l'élément HTML pour modification ultérieure.
    """
    anchors = []

    all_headers = soup.find_all(['h1', 'h2', 'h3', 'h4'])

    logger.debug(f"      Found {len(all_headers)} total headers (h1-h4)")

    for idx, header in enumerate(all_headers):
        anchor_id = header.get('id')
        if not anchor_id:
            header_text = header.get_text(strip=True)
            anchor_id = f"synth-{idx}-{_slugify(header_text)}"

        header_text_display = header.get_text(strip=True)
        logger.debug(f"\n      Processing header #{idx + 1}: '{header_text_display}' ({header.name})")

        scope_text = _extract_header_scope(header, all_headers, idx)
        scope_normalized = _normalize_text_for_comparison(scope_text)

        logger.debug(f"         Scope length: {len(scope_text)} raw, {len(scope_normalized)} normalized")

        if len(scope_normalized) < 50:
            logger.debug(f"         ❌ SKIPPED (scope < 50 chars)")
            continue

        level = int(header.name[1])

        anchors.append({
            'id': anchor_id,
            'tag': header.name,
            'level': level,
            'header_text': header_text_display,
            'scope': scope_normalized,
            'scope_length': len(scope_normalized),
            'has_native_id': header.get('id') is not None,
            'header_element': header  # ✨ NOUVEAU : référence à l'élément HTML
        })

        logger.debug(f"         ✅ KEPT")

    return anchors