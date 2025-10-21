#!/usr/bin/env python3
"""
Script de migration pour nettoyer tous les fichiers markdown dans all_indexes/
Supprime les images base64 et nettoie les espaces inutiles.
"""

import os
import re
import logging
from pathlib import Path
from typing import Tuple

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def clean_markdown_whitespace(markdown_text: str) -> str:
    """
    Nettoie les espaces inutiles et les images base64 dans le markdown pour réduire les tokens.

    - Supprime complètement les images encodées en base64
    - Réduit les séquences d'espaces multiples dans les tableaux
    - Raccourcit les lignes de séparateurs (---, ___, etc.)
    - Conserve la structure du markdown pour qu'il s'affiche correctement
    """
    original_length = len(markdown_text)

    # ✨ ÉTAPE 1 : Supprimer complètement les images base64
    # Pattern pour détecter et supprimer ![texte](data:image/...)
    markdown_text = re.sub(
        r'!\[([^\]]*)\]\(data:image/[^;]+;base64,[A-Za-z0-9+/=]+\)',
        '',  # Suppression complète
        markdown_text
    )

    # Pattern alternatif pour images sans texte alt
    markdown_text = re.sub(
        r'!\[\]\(data:image/[^;]+;base64,[A-Za-z0-9+/=]+\)',
        '',  # Suppression complète
        markdown_text
    )

    # ÉTAPE 2 : Nettoyer les lignes
    lines = markdown_text.splitlines()
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        # Détecter les lignes de séparateurs de tableaux markdown
        if '|' in line and re.match(r'^[\s\|\-_=:]+$', stripped):
            num_pipes = stripped.count('|')
            if num_pipes >= 2:
                separator = '| ' + ' | '.join(['---'] * (num_pipes - 1)) + ' |'
                cleaned_lines.append(separator)
            else:
                cleaned_lines.append(stripped)

        # Lignes de tableaux normales (avec du contenu)
        elif '|' in line:
            cleaned_line = re.sub(r'\s*\|\s*', ' | ', line)
            cleaned_line = re.sub(r'\s{2,}', ' ', cleaned_line)
            cleaned_lines.append(cleaned_line.strip())

        # Autres lignes de séparateurs (headers, etc.)
        elif re.match(r'^[\s\-_=.]+$', stripped):
            if '-' in line:
                cleaned_lines.append('---')
            elif '_' in line:
                cleaned_lines.append('___')
            elif '=' in line:
                cleaned_lines.append('===')
            elif '.' in line:
                cleaned_lines.append('...')
            else:
                cleaned_lines.append(stripped)

        else:
            # Pour les lignes normales, réduire simplement les espaces multiples
            cleaned_line = re.sub(r'\s{3,}', '  ', line)
            cleaned_lines.append(cleaned_line)

    # Réduire les lignes vides consécutives à maximum 2
    result = '\n'.join(cleaned_lines)
    result = re.sub(r'\n{4,}', '\n\n\n', result)

    cleaned_length = len(result)
    reduction_percent = ((original_length - cleaned_length) / original_length * 100) if original_length > 0 else 0

    logger.info(
        f"  📊 Markdown cleaned: {original_length:,} → {cleaned_length:,} chars ({reduction_percent:.1f}% reduction)")

    return result


def process_markdown_file(file_path: Path) -> Tuple[bool, int, int]:
    """
    Traite un fichier markdown unique.

    Args:
        file_path: Chemin vers le fichier markdown

    Returns:
        Tuple (succès, taille_originale, taille_finale)
    """
    try:
        # Lire le contenu original
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()

        original_size = len(original_content)

        # Nettoyer le contenu
        cleaned_content = clean_markdown_whitespace(original_content)
        cleaned_size = len(cleaned_content)

        # Si le contenu a changé, écrire le fichier
        if cleaned_content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_content)
            logger.info(f"✅ Modifié: {file_path}")
            return True, original_size, cleaned_size
        else:
            logger.debug(f"⏭️  Inchangé: {file_path}")
            return True, original_size, cleaned_size

    except Exception as e:
        logger.error(f"❌ Erreur lors du traitement de {file_path}: {e}")
        return False, 0, 0


def migrate_all_markdown_files():
    """
    Parcourt tous les fichiers markdown dans all_indexes et les nettoie.
    """
    # Chemin de base
    base_path = Path(__file__).parent / "../../all_indexes"

    # Vérifier que le dossier existe
    if not base_path.exists():
        logger.error(f"❌ Le dossier {base_path.absolute()} n'existe pas!")
        return

    base_path = base_path.resolve()
    logger.info(f"🚀 Début de la migration dans: {base_path}")

    # Statistiques
    total_files = 0
    processed_files = 0
    modified_files = 0
    failed_files = 0
    total_original_size = 0
    total_cleaned_size = 0

    # Trouver tous les fichiers .md récursivement
    markdown_files = list(base_path.glob("**/*.md"))
    total_files = len(markdown_files)

    if total_files == 0:
        logger.warning("⚠️  Aucun fichier markdown trouvé!")
        return

    logger.info(f"📁 {total_files} fichiers markdown trouvés")
    logger.info("-" * 60)

    # Traiter chaque fichier
    for i, file_path in enumerate(markdown_files, 1):
        logger.info(f"[{i}/{total_files}] Traitement de: {file_path.relative_to(base_path)}")

        success, original_size, cleaned_size = process_markdown_file(file_path)

        if success:
            processed_files += 1
            total_original_size += original_size
            total_cleaned_size += cleaned_size

            if original_size != cleaned_size:
                modified_files += 1
        else:
            failed_files += 1

    # Résumé final
    logger.info("=" * 60)
    logger.info("📊 RÉSUMÉ DE LA MIGRATION")
    logger.info("=" * 60)
    logger.info(f"📁 Total de fichiers trouvés:     {total_files}")
    logger.info(f"✅ Fichiers traités avec succès:  {processed_files}")
    logger.info(f"📝 Fichiers modifiés:             {modified_files}")
    logger.info(f"❌ Fichiers en erreur:            {failed_files}")

    if total_original_size > 0:
        reduction_bytes = total_original_size - total_cleaned_size
        reduction_percent = (reduction_bytes / total_original_size) * 100

        logger.info(f"")
        logger.info(f"💾 Taille totale originale:  {total_original_size:,} octets")
        logger.info(f"💾 Taille totale nettoyée:   {total_cleaned_size:,} octets")
        logger.info(f"📉 Réduction totale:         {reduction_bytes:,} octets ({reduction_percent:.1f}%)")

    if failed_files > 0:
        logger.warning(f"⚠️  {failed_files} fichiers n'ont pas pu être traités. Vérifiez les logs ci-dessus.")

    logger.info("=" * 60)
    logger.info("✨ Migration terminée!")


if __name__ == "__main__":
    try:
        migrate_all_markdown_files()
    except KeyboardInterrupt:
        logger.info("\n⚠️  Migration interrompue par l'utilisateur")
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}", exc_info=True)