"""Global LlamaIndex settings with LiteLLM Proxy integration."""
from llama_index.core import Settings
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from app.config import settings


def configure_llama_settings():
    """Configure LlamaIndex to route through LiteLLM Proxy.
    
    Model names are configured via environment variables:
    - LLM_MODEL: Chat model (default: gpt-4.1-mini)
    - EMBEDDING_MODEL: Embedding model (default: text-embedding-3-small)
    """
    # LLM routed through LiteLLM Proxy
    Settings.llm = OpenAI(
        model=settings.LLM_MODEL,
        temperature=0.1,
        max_tokens=1024,
        api_base=settings.LITELLM_PROXY_URL,
        api_key="sk-fake-key",
    )
    
    # Embeddings routed through LiteLLM Proxy
    Settings.embed_model = OpenAIEmbedding(
        model=settings.EMBEDDING_MODEL,
        api_base=settings.LITELLM_PROXY_URL,
        api_key="sk-fake-key",
        embed_batch_size=100,
    )
    
    print(f"LlamaIndex configured with LiteLLM Proxy at {settings.LITELLM_PROXY_URL}")
    print(f"LLM Model: {settings.LLM_MODEL}")
    print(f"Embedding Model: {settings.EMBEDDING_MODEL}")
