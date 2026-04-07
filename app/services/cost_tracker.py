"""Token counting utility using tiktoken."""
import re

import tiktoken


def _get_encoding():
    """Get a local tiktoken encoding without requiring network fetches."""
    try:
        # cl100k_base is bundled locally and is a good approximation for GPT-4 class models.
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None

# Initialize tokenizer once at module load
enc = _get_encoding()


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken."""
    if not text:
        return 0
    if enc is None:
        return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))
    return len(enc.encode(text))


def count_messages_tokens(messages: list[dict]) -> int:
    """Count tokens in a list of messages."""
    total = 0
    for msg in messages:
        total += count_tokens(msg.get("content", ""))
    return total
