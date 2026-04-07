"""Global LlamaIndex settings and request-scoped overrides."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from llama_index.core import Settings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI

from app.config import settings


_settings_lock = asyncio.Lock()


def build_llm(api_key: str | None = None) -> OpenAI:
    """Build the chat model using either a request key or the default proxy."""
    kwargs = {
        "model": settings.LLM_MODEL,
        "temperature": 0.1,
        "max_tokens": 1024,
    }
    if api_key:
        kwargs["api_key"] = api_key
    else:
        kwargs["api_base"] = settings.LITELLM_PROXY_URL
        kwargs["api_key"] = "sk-fake-key"
    return OpenAI(**kwargs)


def build_embed_model(api_key: str | None = None) -> OpenAIEmbedding:
    """Build the embedding model using either a request key or the default proxy."""
    kwargs = {
        "model": settings.EMBEDDING_MODEL,
        "embed_batch_size": 100,
    }
    if api_key:
        kwargs["api_key"] = api_key
    else:
        kwargs["api_base"] = settings.LITELLM_PROXY_URL
        kwargs["api_key"] = "sk-fake-key"
    return OpenAIEmbedding(**kwargs)


def configure_llama_settings(api_key: str | None = None) -> None:
    """Configure global default LlamaIndex settings."""
    Settings.llm = build_llm(api_key=api_key)
    Settings.embed_model = build_embed_model(api_key=api_key)

    if api_key:
        print("LlamaIndex configured with direct OpenAI access from request-scoped key")
    else:
        print(f"LlamaIndex configured with LiteLLM Proxy at {settings.LITELLM_PROXY_URL}")
    print(f"LLM Model: {settings.LLM_MODEL}")
    print(f"Embedding Model: {settings.EMBEDDING_MODEL}")


@asynccontextmanager
async def temporary_llama_settings(api_key: str | None = None) -> AsyncIterator[None]:
    """Temporarily swap global LlamaIndex clients for request-scoped API keys."""
    if not api_key:
        yield
        return

    async with _settings_lock:
        previous_llm = Settings.llm
        previous_embed_model = Settings.embed_model
        Settings.llm = build_llm(api_key=api_key)
        Settings.embed_model = build_embed_model(api_key=api_key)
        try:
            yield
        finally:
            Settings.llm = previous_llm
            Settings.embed_model = previous_embed_model
