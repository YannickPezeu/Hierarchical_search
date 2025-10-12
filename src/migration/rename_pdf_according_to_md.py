import os
from rapidfuzz import process, fuzz

# --- CONFIGURATION ---
# Mettez à jour ces chemins si nécessaire
MD_DIR = r"../../all_indexes/test_enrichment/md_files"
PDF_DIR = r"../../all_indexes/test_enrichment/source_files"
CONFIDENCE_THRESHOLD = 85  # Ne renomme que si la similarité est > 85%
DRY_RUN = False  # True = Affiche ce qui serait fait, False = Exécute le renommage


def sync_pdf_filenames_to_md():
    """
    Synchronise les noms des fichiers PDF pour qu'ils correspondent
    à leurs fichiers Markdown les plus similaires.
    """
    print("=" * 80)
    print("SCRIPT DE SYNCHRONISATION DES NOMS DE FICHIERS PDF -> MD")
    print("=" * 80)

    if DRY_RUN:
        print("⚠️  MODE SIMULATION (DRY RUN) ACTIVÉ. Aucun fichier ne sera renommé.")
    else:
        print("🔴 MODE ACTIF. Les fichiers PDF seront renommés.")

    print(f"\n📁 Dossier des Markdown (source de vérité) : '{MD_DIR}'")
    print(f"📁 Dossier des PDF (à corriger) : '{PDF_DIR}'")
    print("-" * 80)

    # 1. Lister les fichiers et extraire les noms de base (sans extension)
    try:
        md_files = [f for f in os.listdir(MD_DIR) if f.endswith('.md')]
        pdf_files = [f for f in os.listdir(PDF_DIR) if f.endswith('.pdf')]

        md_basenames = [os.path.splitext(f)[0] for f in md_files]
        pdf_basenames = [os.path.splitext(f)[0] for f in pdf_files]

        if not md_files or not pdf_files:
            print("❌ Erreur: Un des dossiers est vide ou introuvable. Arrêt du script.")
            return

    except FileNotFoundError:
        print(f"❌ Erreur: Un des chemins de dossier est incorrect. Vérifiez la configuration.")
        return

    # 2. Pour chaque MD, trouver le meilleur match PDF et renommer si nécessaire
    total_renamed = 0
    for i, md_basename in enumerate(md_basenames):

        print(f"\n[{i + 1}/{len(md_basenames)}] Traitement de : '{md_basename}.md'")

        # Utilise rapidfuzz pour trouver le meilleur match dans la liste des noms de base PDF
        best_match = process.extractOne(md_basename, pdf_basenames, scorer=fuzz.ratio)

        if not best_match:
            print("  -> Aucun match trouvé.")
            continue

        best_pdf_basename, score, _ = best_match
        score = round(score)

        print(f"  -> Meilleur match trouvé : '{best_pdf_basename}.pdf' (Score: {score}%)")

        # 3. Décider s'il faut renommer
        if md_basename == best_pdf_basename:
            print("  ✅ Noms déjà synchronisés.")
        elif score < CONFIDENCE_THRESHOLD:
            print(f"  ⚠️ Action ignorée : score de confiance ({score}%) trop faible (seuil: {CONFIDENCE_THRESHOLD}%).")
        else:
            old_pdf_path = os.path.join(PDF_DIR, best_pdf_basename + '.pdf')
            new_pdf_path = os.path.join(PDF_DIR, md_basename + '.pdf')

            # Sécurité : vérifier si le nouveau nom existe déjà
            if os.path.exists(new_pdf_path):
                print(f"  ⚠️ Action ignorée : le fichier cible '{md_basename}.pdf' existe déjà.")
            else:
                action_prefix = "DRY RUN: Renommerait" if DRY_RUN else "RENOMMAGE:"
                print(f"  -> {action_prefix} '{best_pdf_basename}.pdf' en '{md_basename}.pdf'")

                if not DRY_RUN:
                    try:
                        os.rename(old_pdf_path, new_pdf_path)
                        total_renamed += 1
                    except Exception as e:
                        print(f"  ❌ ERREUR lors du renommage : {e}")

    print("\n" + "-" * 80)
    print("✨ Synchronisation terminée.")
    if DRY_RUN:
        print("Aucun fichier n'a été modifié. Passez DRY_RUN à False pour appliquer les changements.")
    else:
        print(f"{total_renamed} fichier(s) PDF ont été renommés.")
    print("=" * 80)


if __name__ == "__main__":
    sync_pdf_filenames_to_md()