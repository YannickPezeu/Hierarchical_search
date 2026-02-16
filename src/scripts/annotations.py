# check_annotations.py (version 3 - finale)
import os
import json
import argparse
import logging
from llama_index.core.schema import NodeRelationship

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Pris en compte de votre modification
ALL_INDEXES_DIR = "../../all_indexes"

def find_unannotated_nodes(index_id: str):
    """
    Charge un index, parcourt le docstore et identifie les child nodes
    qui n'ont pas de métadonnée 'node_anchor_id'.
    """
    index_path = os.path.join(ALL_INDEXES_DIR, index_id)
    docstore_path = os.path.join(index_path, "index", "docstore.json")

    if not os.path.exists(docstore_path):
        logging.error(f"Le fichier docstore.json est introuvable : {docstore_path}")
        return

    logging.info(f"Chargement direct du fichier : {docstore_path}")
    try:
        with open(docstore_path, 'r', encoding='latin-1') as f:
            docstore_data = json.load(f)

        # ▼▼▼ LA CORRECTION FINALE EST ICI ▼▼▼
        # On utilise la clé exacte révélée par votre log d'erreur.
        nodes_dict = None
        if "docstore/data" in docstore_data and isinstance(docstore_data["docstore/data"], dict):
            nodes_dict = docstore_data["docstore/data"]
        # On garde les anciens checks au cas où pour d'autres versions d'index
        elif "docs" in docstore_data and isinstance(docstore_data["docs"], dict):
            nodes_dict = docstore_data["docs"]
        elif "__data__" in docstore_data and isinstance(docstore_data["__data__"], dict):
            nodes_dict = docstore_data["__data__"]
        else:
            logging.error("Impossible de trouver le dictionnaire principal des nœuds ('docstore/data', 'docs' ou '__data__') dans docstore.json.")
            logging.error(f"Clés trouvées au premier niveau : {list(docstore_data.keys())}")
            return

        all_serialized_nodes = list(nodes_dict.values())
        # ▲▲▲ FIN DE LA CORRECTION ▲▲▲

        logging.info(f"✅ Docstore chargé et parsé avec succès, contenant {len(all_serialized_nodes)} nodes au total.")

    except Exception as e:
        logging.error(f"Erreur lors du chargement ou du parsing de docstore.json : {e}", exc_info=True)
        return

    # --- Identification des nodes ---
    unannotated_nodes_info = []
    parent_rel_key = str(NodeRelationship.PARENT.value)

    for node_data in all_serialized_nodes:
        relationships = node_data.get("relationships", {})
        if parent_rel_key in relationships:
            metadata = node_data.get("metadata", {})
            if 'node_anchor_id' not in metadata:
                unannotated_nodes_info.append({
                    "id": node_data.get("id_", "N/A"),
                    "file_name": metadata.get('file_name', 'N/A'),
                    "text": node_data.get("text", ""),
                })

    # --- Affichage des résultats ---
    print("\n" + "=" * 80)
    print("RÉSULTAT DE L'ANALYSE D'ANNOTATION")
    print("=" * 80)

    logging.info(f"Total de nodes non annotés trouvés : {len(unannotated_nodes_info)}")

    if not unannotated_nodes_info:
        print("\n✅ Tous les child nodes semblent être correctement annotés.")
    else:
        print(f"\n❌ {len(unannotated_nodes_info)} child node(s) non annoté(s) trouvé(s) :\n")
        for i, node_info in enumerate(unannotated_nodes_info):
            print("-" * 50)
            print(f"  NODE NON ANNOTÉ N°{i + 1}")
            print("-" * 50)
            print(f"  ID du node   : {node_info['id']}")
            print(f"  Fichier source : {node_info['file_name']}")
            print(f"  Taille du texte  : {len(node_info['text'])} caractères")
            print("\n  Aperçu du texte :")
            print(f"  ------------------")
            print(node_info['text'][:400].strip() + "...")
            print("\n")

    print("=" * 80)


if __name__ == '__main__':
    # Pris en compte de votre modification pour un test direct
    find_unannotated_nodes("test_enrichment")