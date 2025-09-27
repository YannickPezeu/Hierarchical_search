from dotenv import load_dotenv
load_dotenv()  # Load environment variables from a .env file if present
import os
import httpx

from llama_index.core import Settings
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding

# v-- IMPORTATION AJOUTÉE --v
from llama_index.core.node_parser import MarkdownNodeParser
# ^-- IMPORTATION AJOUTÉE --^


class CustomOpenAIEmbedding(OpenAIEmbedding):
    """
    This custom class tricks the parent constructor into succeeding by passing
    a valid model name, and then immediately overwrites the internal engine
    names with the user's actual custom model.
    """
    def __init__(self, model: str, **kwargs):
        super().__init__(model="text-embedding-ada-002", **kwargs)
        self._query_engine = model
        self._text_engine = model
        self.model_name = model


def init_settings():
    """
    Initializes LlamaIndex settings to use a custom OpenAI-compatible endpoint
    and a MarkdownNodeParser for chunking.
    """
    # api_base = os.getenv("OPENAI_API_ENDPOINT")
    # api_key = os.getenv("OPENAI_KEY")

    api_base = os.getenv("RCP_API_ENDPOINT")
    api_key = os.getenv("RCP_API_KEY")

    if not api_key:
        raise ValueError("OPENAI_KEY is missing in environment variables")
    if not api_base:
        raise ValueError("OPENAI_API_ENDPOINT is missing in environment variables")

    # llm_model = os.getenv("RCP_MISTRAL_3_2_MODEL", "gpt-4o")
    llm_model = 'gpt-4o-mini'
    embedding_model = os.getenv("RCP_QWEN_EMBEDDING_MODEL")

    print('embedding_model', embedding_model)
    print('api_base', api_base)
    print('api_key', api_key[:4] + '...' + api_key[-4:])
    print('llm_model', llm_model)

    # --- Configuration du LLM ---
    Settings.llm = OpenAI(
        model=llm_model,
        api_key=api_key,
        api_base=api_base,
    )

    # --- Configuration du modèle d'embedding ---
    Settings.embed_model = CustomOpenAIEmbedding(
        model=embedding_model,
        api_key=api_key,
        api_base=api_base,
        num_workers=1,
    )
    
    # v-- NOUVELLES LIGNES POUR LE PARSER --v
    # --- Configuration du Node Parser ---
    # On définit le MarkdownNodeParser comme parser par défaut pour tout le projet.
    Settings.node_parser = MarkdownNodeParser(
        include_metadata=True,      # Pour inclure les titres de section dans les métadonnées
        include_prev_next_rel=True, # Pour lier les nodes entre eux
    )
    print("Default node_parser set to: MarkdownNodeParser")
    # ^-- FIN DES NOUVELLES LIGNES --^


    print("\n✅ LlamaIndex settings initialized successfully.")

# --- Example Usage ---
if __name__ == "__main__":
    init_settings()

    # Maintenant, LlamaIndex utilisera automatiquement le MarkdownNodeParser
    # lors de la création d'un index si aucun autre parser n'est spécifié.