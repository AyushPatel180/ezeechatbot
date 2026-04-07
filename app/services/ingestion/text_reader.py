"""Plain text ingestion reader."""
from typing import List
from llama_index.core.schema import Document


class TextReader:
    """Simple text ingestion — wraps plain text into a LlamaIndex Document."""

    def load(self, content: str, bot_id: str) -> List[Document]:
        """
        Create document from plain text.

        Args:
            content: Plain text content
            bot_id: Bot identifier for metadata

        Returns:
            List with single LlamaIndex Document
        """
        if not content or len(content.strip()) < 10:
            raise ValueError("Text content too short (minimum 10 characters)")

        doc = Document(
            text=content.strip(),
            metadata={
                "bot_id": bot_id,
                "source_type": "text",
            },
        )
        # Don't dilute embedding with the bot UUID
        doc.excluded_embed_metadata_keys = ["bot_id"]

        return [doc]


# Singleton instance
text_reader = TextReader()
