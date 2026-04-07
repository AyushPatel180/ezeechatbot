"""Typed exception hierarchy for EzeeChatBot."""


class EzeeChatBotError(Exception):
    """Base exception for all EzeeChatBot errors."""
    pass


class BotNotFoundError(EzeeChatBotError):
    """Raised when a bot_id is not found."""
    pass


class NoExtractableContentError(EzeeChatBotError):
    """Raised when no content can be extracted from source."""
    pass


class LLMGenerationError(EzeeChatBotError):
    """Raised when LLM generation fails."""
    pass


class RetrievalError(EzeeChatBotError):
    """Raised when vector retrieval fails."""
    pass


class IngestionError(EzeeChatBotError):
    """Raised when document ingestion fails."""
    pass
