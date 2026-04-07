"""FastAPI application with lifespan management."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
except ImportError:
    class RateLimitExceeded(Exception):
        """Fallback rate-limit exception when slowapi is unavailable."""

    class Limiter:  # pragma: no cover - compatibility shim
        """No-op limiter so the app can still boot without slowapi."""

        def __init__(self, *args, **kwargs):
            pass

    def get_remote_address(request: Request) -> str:
        return request.client.host if request.client else "unknown"


# EARLY IMPORT VALIDATION - catch module errors at startup
try:

    # LlamaIndex imports
    from llama_index.core import Settings, VectorStoreIndex, StorageContext
    from llama_index.core.llms import ChatMessage, MessageRole
    from llama_index.core.chat_engine.condense_plus_context import CondensePlusContextChatEngine
    from llama_index.core.postprocessor import SimilarityPostprocessor
    from llama_index.core.retrievers import VectorIndexRetriever
    from llama_index.core.ingestion import IngestionPipeline
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.vector_stores.qdrant import QdrantVectorStore
    from llama_index.llms.openai import OpenAI
    from llama_index.embeddings.openai import OpenAIEmbedding

    # Qdrant
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Distance, VectorParams, PayloadSchemaType

    IMPORTS_OK = True
    IMPORT_ERROR = None
except ImportError as e:
    IMPORTS_OK = False
    IMPORT_ERROR = str(e)
    print(f"CRITICAL: Import error during startup: {e}")
    raise

from app.core.qdrant_client import init_qdrant
from app.core.llama_settings import configure_llama_settings
from app.core.langfuse_handler import setup_langfuse_callback
from app.db.database import init_db
from app.routers import upload, chat, stats, health
from app.utils.errors import EzeeChatBotError, BotNotFoundError
from app.utils.logger import configure_logging, get_logger

# Configure logging on startup
configure_logging()
logger = get_logger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("starting EzeeChatBot", phase="startup")

    try:
        # Configure LlamaIndex with LiteLLM Proxy
        configure_llama_settings()
        logger.info("llama_settings configured", phase="startup")

        # Setup observability
        setup_langfuse_callback()
        logger.info("langfuse configured", phase="startup")

        # Initialize Qdrant
        init_qdrant()
        logger.info("qdrant initialized", phase="startup")

        # Initialize database
        await init_db()
        logger.info("database initialized", phase="startup")

        logger.info("startup complete", phase="startup", status="success")
    except Exception as e:
        logger.error("startup failed", phase="startup", error=str(e))
        raise

    yield

    # Shutdown
    logger.info("shutting down", phase="shutdown")


# Create FastAPI app
app = FastAPI(
    title="EzeeChatBot API",
    description="Multi-tenant RAG Chatbot API with LiteLLM integration",
    version="1.0.0",
    lifespan=lifespan,
)

# Add rate limiter
app.state.limiter = limiter


# Exception handlers
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    logger.warning(
        "rate_limit_exceeded",
        path=request.url.path,
        client=request.client.host if request.client else None,
    )
    return JSONResponse(
        status_code=429,
        content={"error": "rate_limit_exceeded", "message": "Too many requests. Please slow down."},
    )


@app.exception_handler(BotNotFoundError)
async def bot_not_found_handler(request: Request, exc: BotNotFoundError):
    logger.warning("bot_not_found", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=404,
        content={"error": "bot_not_found", "message": str(exc)},
    )


@app.exception_handler(EzeeChatBotError)
async def generic_error_handler(request: Request, exc: EzeeChatBotError):
    logger.error("internal_error", path=request.url.path, error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": str(exc)},
    )


# Include routers
app.include_router(upload.router, tags=["Upload"])
app.include_router(chat.router, tags=["Chat"])
app.include_router(stats.router, tags=["Stats"])
app.include_router(health.router, tags=["Health"])


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "EzeeChatBot API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
