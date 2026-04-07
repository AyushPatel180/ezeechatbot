"""Langfuse callback handler for observability."""
import os
from app.config import settings


def setup_langfuse_callback():
    """Set up Langfuse observability via environment variables.

    LiteLLM proxy picks up Langfuse credentials from these env vars automatically.
    We also set them here so any direct litellm calls in the API container are
    traced as well.
    """
    if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
        # Set env vars — the canonical way to configure the Langfuse callback
        # for both the litellm package and the LiteLLM proxy
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.LANGFUSE_PUBLIC_KEY)
        os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.LANGFUSE_SECRET_KEY)
        os.environ.setdefault("LANGFUSE_HOST", settings.LANGFUSE_HOST)
        print("Langfuse observability enabled")
    else:
        print("Langfuse not configured (missing credentials) — skipping")
