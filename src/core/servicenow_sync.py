# src/core/servicenow_sync.py
import os
import json
import logging
import requests
import re
from requests.auth import HTTPBasicAuth
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from typing import List, Dict

from src.core.utils import get_index_path, get_password_hash
from src.core.indexing import run_indexing_logic

logger = logging.getLogger(__name__)

# Config ServiceNow (à charger depuis .env)
SN_USERNAME = "WS_AI"  # Ou os.getenv("SERVICENOW_USER")
SN_PASSWORD = os.getenv("SERVICENOW_KEY")
BASE_URL = "https://epfl.service-now.com/api/now/table/kb_knowledge"


def sanitize_html_for_source(raw_html: str) -> str:
    """
    Nettoyage 'Doux' pour l'archive source HTML.
    OBJECTIF : Garder le texte visible STRICTEMENT identique au site live
    pour que les Text-Fragments fonctionnent.
    """
    if not raw_html:
        return ""

    soup = BeautifulSoup(raw_html, 'html.parser')

    # 1. Supprimer les éléments invisibles/dangereux
    for tag in soup(['script', 'style', 'noscript', 'iframe', 'meta', 'link', 'form', 'input', 'button']):
        tag.decompose()

    # 2. Nettoyer les attributs (garder href, src, id, mais virer les styles inline, onclick, etc.)
    # Cela évite de casser le DOM mais retire le bruit.
    allowed_attrs = ['href', 'src', 'alt', 'title', 'id', 'name', 'rowspan', 'colspan']

    for tag in soup.find_all(True):
        # On fait une copie des clés pour pouvoir supprimer en itérant
        attrs = dict(tag.attrs)
        for attr in attrs:
            if attr not in allowed_attrs:
                del tag.attrs[attr]

    return str(soup)


def fetch_articles_from_kb(kb_id: str) -> List[Dict]:
    """Récupère tous les articles publiés d'une KB spécifique via l'API."""
    articles = []
    offset = 0
    limit = 100

    # Query: KB spécifique + Publié + Actif
    # On ajoute display_value=true pour avoir les noms des catégories/KB lisibles
    params = {
        "sysparm_query": f"kb_knowledge_base={kb_id}^workflow_state=published^active=true",
        "sysparm_display_value": "true",
        "sysparm_limit": limit,
        "sysparm_offset": offset,
        "sysparm_fields": "sys_id,number,short_description,text,kb_category,sys_updated_on"
    }

    logger.info(f"🔄 Fetching ServiceNow articles for KB: {kb_id}")

    while True:
        params["sysparm_offset"] = offset
        try:
            response = requests.get(
                BASE_URL,
                params=params,
                auth=HTTPBasicAuth(SN_USERNAME, SN_PASSWORD),
                headers={"Accept": "application/json"}
            )

            if response.status_code != 200:
                logger.error(f"❌ Error fetching SN articles: {response.status_code} - {response.text}")
                break

            data = response.json()
            batch = data.get('result', [])

            if not batch:
                break

            articles.extend(batch)
            offset += limit
            logger.info(f"   ...fetched {len(articles)} articles so far")

        except Exception as e:
            logger.error(f"❌ Exception fetching SN articles: {e}")
            break

    return articles


def servicenow_ingestion_task(index_id: str, kb_ids: List[str], user_groups: List[str] = None):
    """
    Tâche principale d'ingestion ServiceNow -> RAG.
    Remplace index_creation_task pour ce flux spécifique.
    """
    logger.info(f"🚀 Starting ServiceNow Ingestion for index: {index_id}")

    index_path = get_index_path(index_id)
    source_files_archive = os.path.join(index_path, "source_files_archive")
    md_files_dir = os.path.join(index_path, "md_files")

    # Création des dossiers
    os.makedirs(source_files_archive, exist_ok=True)
    os.makedirs(md_files_dir, exist_ok=True)

    # Sauvegarde des groupes si fournis
    if user_groups:
        groups_file = os.path.join(index_path, ".groups.json")
        with open(groups_file, "w") as f:
            json.dump({"groups": user_groups}, f)

    total_processed = 0

    for kb_id in kb_ids:
        articles = fetch_articles_from_kb(kb_id)

        for article in articles:
            try:
                # 1. Extraction des données
                sys_id = article.get('sys_id')
                number = article.get('number', 'UNKNOWN')  # ex: KB0012345
                title = article.get('short_description', 'No Title')
                raw_html = article.get('text', '')

                # Gestion de la catégorie pour le dossier (ex: "IT > Email")
                category_obj = article.get('kb_category')
                category_name = "General"
                if isinstance(category_obj, dict):
                    category_name = category_obj.get('display_value', 'General')
                elif isinstance(category_obj, str):
                    category_name = category_obj

                # Nettoyage du nom de catégorie pour le filesystem
                safe_category = re.sub(r'[^\w\s-]', '', category_name).strip().replace(' ', '_')

                # 2. Chemins de fichiers
                # On structure : servicenow / Category / KBxxxx.html
                relative_dir = os.path.join("servicenow", safe_category)
                filename_base = number

                # Chemins complets
                archive_dir_full = os.path.join(source_files_archive, relative_dir)
                md_dir_full = os.path.join(md_files_dir, relative_dir)

                os.makedirs(archive_dir_full, exist_ok=True)
                os.makedirs(md_dir_full, exist_ok=True)

                # 3. Traitement HTML Source (Soft Clean)
                # On ajoute le titre en H1 car il n'est pas dans le champ 'text' mais est affiché sur le portail
                clean_html_content = sanitize_html_for_source(raw_html)
                full_html_source = f"<h1>{title}</h1>\n{clean_html_content}"

                html_path = os.path.join(archive_dir_full, f"{filename_base}.html")
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(full_html_source)

                # 4. Conversion Markdown (Pour l'IA)
                # On utilise markdownify sur le HTML nettoyé
                md_content = md(full_html_source, heading_style="ATX")

                # Ajout d'en-tête de métadonnées Markdown si utile pour le LLM
                md_content = f"# {title}\n\nReference: {number}\n\n{md_content}"

                md_path = os.path.join(md_dir_full, f"{filename_base}.md")
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(md_content)

                # 5. Création du fichier .meta (Mapping URL)
                # C'est ICI qu'on fait le lien vers le portail public
                public_url = f"https://support.epfl.ch/epfl?id=epfl_kb_article_view&sys_kb_id={sys_id}"

                meta_path = md_path + ".meta"
                meta_data = {
                    "source_url": public_url,
                    "source_filename": f"{filename_base}.html",
                    "source_relative_path": os.path.join(relative_dir, f"{filename_base}.html").replace("\\", "/"),
                    "sys_id": sys_id,
                    "kb_number": number,
                    "updated_at": article.get('sys_updated_on')
                }

                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta_data, f, indent=2)

                total_processed += 1

            except Exception as e:
                logger.error(f"❌ Error processing article {article.get('number')}: {e}")
                continue

    logger.info(f"✅ ServiceNow Ingestion: Processed {total_processed} articles. Starting Indexing...")

    # 6. Lancement de l'indexation standard
    # On réutilise votre logique existante qui va scanner md_files/ et calculer les ancres
    index_dir = os.path.join(index_path, "index")
    try:
        run_indexing_logic(source_md_dir=md_files_dir, index_dir=index_dir)

        # Mettre à jour le statut
        status_file = os.path.join(index_path, ".indexing_status")
        with open(status_file, "w") as f:
            json.dump({
                "status": "completed",
                "num_documents": total_processed,
                "type": "servicenow_sync"
            }, f)

    except Exception as e:
        logger.error(f"❌ Error during indexing phase: {e}")
        status_file = os.path.join(index_path, ".indexing_status")
        with open(status_file, "w") as f:
            json.dump({"status": "failed", "error": str(e)}, f)