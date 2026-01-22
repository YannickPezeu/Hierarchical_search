# src/core/servicenow_live.py
import os
import re
import math
import logging
import requests
from bs4 import BeautifulSoup
from typing import List

# On importe le modèle de réponse défini plus bas (ou depuis src/core/servicenow_models.py)
from src.core.servicenow_models import ServiceNowSearchResult

logger = logging.getLogger(__name__)

# --- Configuration adaptée à vos variables .env ---
SN_URL = os.getenv("SERVICENOW_URL", "https://epfl.service-now.com")
SN_USER = os.getenv("SERVICENOW_USERNAME", "WS_AI")
# Utilisation de SERVICENOW_KEY
SN_PWD = os.getenv("SERVICENOW_KEY", "")

# Utilisation de SERVICENOW_KB_IDS_FINANCE comme défaut
DEFAULT_KB_IDS_RAW = os.getenv("SERVICENOW_KB_IDS_FINANCE", "")

RCP_ENDPOINT = os.getenv("RCP_API_ENDPOINT", "https://inference.rcp.epfl.ch/v1")
RCP_KEY = os.getenv("RCP_API_KEY", "")
# Utilisation de RCP_QWEN_EMBEDDING_MODEL
EMBEDDING_MODEL = os.getenv("RCP_QWEN_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")


FRENCH_STOPWORDS = {
    # Pronoms
    "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
    "me", "te", "se", "moi", "toi", "lui", "leur", "eux", "ce", "ceci", "cela", "ca",
    # Articles & Déterminants
    "le", "la", "les", "l", "un", "une", "des", "du", "de", "d", "au", "aux",
    "mon", "ton", "son", "ma", "ta", "sa", "mes", "tes", "ses",
    "notre", "votre", "nos", "vos", "leurs",
    "ce", "cet", "cette", "ces",
    # Prépositions & Conjonctions
    "et", "ou", "mais", "donc", "or", "ni", "car",
    "a", "à", "dans", "par", "pour", "en", "vers", "avec", "sans", "sous", "sur", "chez",
    # Verbes d'état / Auxiliaires (formes simples)
    "est", "sont", "suis", "es", "etes", "etais", "etait", "faut", "doit",
    "ai", "as", "a", "ont", "avons", "avez", "avoir", "etre", "faire", "aller",
    # Mots de requête courants (bruit)
    "comment", "pourquoi", "quand", "qui", "que", "quoi", "ou", "quel", "quelle", "quels", "quelles",
    "est-ce", "qu'est-ce", "s'il", "plait", "bonjour", "merci", "salut", "chercher", "trouver"
}

class MarkdownSplitter:
    def __init__(self, chunk_size=1500, chunk_overlap=200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        separators = [r"\n#{1,6} ", r"\n\n", r"\n", r" ", r""]
        return self._recursive_split(text, separators)

    def _recursive_split(self, text: str, separators: List[str]) -> List[str]:
        final_chunks = []
        if not separators or len(text) < self.chunk_size:
            return [text]

        separator = separators[0]
        next_separators = separators[1:]

        if separator == "":
            splits = list(text)
        else:
            splits = re.split(f"({separator})", text)

        current_chunk = []
        current_length = 0

        for split in splits:
            if not split: continue
            if separator and re.match(separator, split):
                current_chunk.append(split)
                current_length += len(split)
                continue

            if current_length + len(split) > self.chunk_size:
                if current_chunk:
                    doc = "".join(current_chunk).strip()
                    if doc: final_chunks.append(doc)

                    if self.chunk_overlap > 0 and len(doc) > self.chunk_overlap:
                        overlap_len = min(len(doc), self.chunk_overlap)
                        current_chunk = [doc[-overlap_len:]]
                        current_length = len(current_chunk[0])
                    else:
                        current_chunk = []
                        current_length = 0

                if len(split) > self.chunk_size:
                    final_chunks.extend(self._recursive_split(split, next_separators))
                else:
                    current_chunk.append(split)
                    current_length += len(split)
            else:
                current_chunk.append(split)
                current_length += len(split)

        if current_chunk:
            doc = "".join(current_chunk).strip()
            if doc: final_chunks.append(doc)

        return final_chunks


class ServiceNowLiveEngine:
    def __init__(self):
        self.splitter = MarkdownSplitter()

    def _clean_kb_ids(self, kb_ids_str: str) -> str:
        """
        Nettoie la chaîne d'IDs pour gérer le format liste [id1, id2] ou CSV simple.
        """
        if not kb_ids_str:
            return ""
        # Enlever les crochets, les guillemets simples/doubles et les espaces
        cleaned = kb_ids_str.replace("[", "").replace("]", "").replace("'", "").replace('"', "").replace(" ", "")
        return cleaned

    def _extract_clean_text(self, html_content: str) -> str:
        if not html_content: return ""
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            for tag in soup.select("script, style"): tag.decompose()

            for header in soup.find_all(["h1", "h2", "h3", "h4"]):
                level = int(header.name[1])
                header.replace_with(f"\n\n{'#' * level} {header.get_text().strip()}\n")

            for li in soup.find_all("li"):
                li.replace_with(f"- {li.get_text().strip()}\n")

            for table in soup.find_all("table"):
                rows = []
                for tr in table.find_all("tr"):
                    cells = [td.get_text().strip() for td in tr.find_all(["td", "th"])]
                    rows.append(" | ".join(cells))
                table.replace_with("\n" + "\n".join(rows) + "\n")

            text = soup.get_text()
            return re.sub(r"\n{3,}", "\n\n", text).strip()
        except Exception as e:
            logger.warning(f"HTML parsing error: {e}")
            return re.sub(r"<[^>]+>", "", html_content).strip()

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts: return []

        url = RCP_ENDPOINT
        if not url.endswith("/embeddings"):
            url = f"{url.rstrip('/')}/embeddings"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {RCP_KEY}",
        }

        # Utilisation de la variable EMBEDDING_MODEL configurée
        payload = {"input": texts, "model": EMBEDDING_MODEL}

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "data" in data:
                data["data"].sort(key=lambda x: x["index"])
                return [item["embedding"] for item in data["data"]]
            return []
        except Exception as e:
            logger.error(f"RCP Embedding Error: {e}")
            return []

    def _cosine_similarity(self, vec1, vec2) -> float:
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm_a = math.sqrt(sum(a * a for a in vec1))
        norm_b = math.sqrt(sum(b * b for b in vec2))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0

    def search(self, query: str, kb_ids: str = None, top_k: int = 5) -> List[ServiceNowSearchResult]:
        if not SN_PWD:
            logger.error("SERVICENOW_KEY not set in environment")
            raise ValueError("ServiceNow configuration missing (SERVICENOW_KEY)")

        # Gestion des IDs
        raw_ids = kb_ids if kb_ids else DEFAULT_KB_IDS_RAW
        target_kbs = self._clean_kb_ids(raw_ids)

        # --- MODIFICATION ICI : FILTRAGE INTELLIGENT ---

        # 1. Découpage en mots (tokenization simple)
        # On passe en minuscule pour comparer avec la liste
        words = re.findall(r"\w+", query.lower())

        # 2. Filtrage des stopwords
        filtered_words = [w for w in words if w not in FRENCH_STOPWORDS]

        # 3. Reconstruction de la requête
        # Si le filtrage a tout supprimé (ex: l'utilisateur a juste tapé "le la"), on garde la requête originale
        if filtered_words:
            keywords = " ".join(filtered_words)
        else:
            keywords = query

        # 2. Appel API ServiceNow
        sysparm_query = f"kb_knowledge_baseIN{target_kbs}^workflow_state=published^active=true^123TEXTQUERY321={keywords}"

        base_url = SN_URL.rstrip("/")
        url = f"{base_url}/api/now/table/kb_knowledge"

        params = {
            "sysparm_query": sysparm_query,
            "sysparm_limit": 10,
            "sysparm_fields": "sys_id,short_description,text,kb_knowledge_base",
            "sysparm_display_value": "all"
        }

        logger.info(f"Fetching ServiceNow KBs (query: {keywords}, KBs: {target_kbs})")

        try:
            resp = requests.get(
                url,
                params=params,
                auth=(SN_USER, SN_PWD),
                headers={"Accept": "application/json"},
                timeout=15
            )
            resp.raise_for_status()
            articles = resp.json().get("result", [])
        except Exception as e:
            logger.error(f"ServiceNow API failed: {e}")
            raise RuntimeError(f"ServiceNow fetch failed: {e}")

        if not articles:
            return []

        # 3. Processing & Chunking
        chunks_text = []
        chunks_meta = []

        for art in articles:
            raw_html = art["text"]["display_value"]
            clean_text = self._extract_clean_text(raw_html)
            title = art["short_description"]["display_value"]
            kb_name = art["kb_knowledge_base"]["display_value"]
            sys_id = art["sys_id"]["value"]
            public_url = f"https://support.epfl.ch/epfl?id=epfl_kb_article_view&sys_kb_id={sys_id}"

            art_chunks = self.splitter.split_text(clean_text)

            for chunk in art_chunks:
                contextualized_chunk = f"Title: {title}\nKB: {kb_name}\nContent: {chunk}"
                chunks_text.append(contextualized_chunk)
                chunks_meta.append({
                    "title": title,
                    "url": public_url,
                    "kb_name": kb_name,
                    "raw_chunk": chunk
                })

        if not chunks_text:
            return []

        # 4. Embedding & Ranking
        logger.info(f"Embedding {len(chunks_text)} chunks with model {EMBEDDING_MODEL}...")
        all_texts = [query] + chunks_text
        vectors = self._get_embeddings(all_texts)

        if not vectors or len(vectors) < 2:
            logger.warning("Embedding failed or returned empty")
            return []

        query_vec = vectors[0]
        doc_vecs = vectors[1:]

        scored_results = []
        for i, vec in enumerate(doc_vecs):
            score = self._cosine_similarity(query_vec, vec)
            scored_results.append((score, i))

        scored_results.sort(key=lambda x: x[0], reverse=True)
        top_results = scored_results[:top_k]

        final_results = []
        for score, idx in top_results:
            meta = chunks_meta[idx]
            final_results.append(ServiceNowSearchResult(
                title=meta["title"],
                content=meta["raw_chunk"],
                url=meta["url"],
                kb_name=meta["kb_name"],
                score=score
            ))

        return final_results