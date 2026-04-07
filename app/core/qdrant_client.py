"""Singleton Qdrant client with collection and index initialization."""
from functools import lru_cache
from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.http.models import Distance, VectorParams, PayloadSchemaType
from llama_index.vector_stores.qdrant import QdrantVectorStore
from app.config import settings


COLLECTION_NAME = "ezeechatbot_nodes"
EMBEDDING_DIM = 1536  # text-embedding-3-small


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """Get singleton Qdrant client."""
    return QdrantClient(url=settings.QDRANT_URL)


def init_qdrant():
    """Initialize Qdrant collection and indexes on startup."""
    client = get_qdrant_client()
    
    # Check if collection exists
    existing = [c.name for c in client.get_collections().collections]
    
    if COLLECTION_NAME not in existing:
        # Create collection with cosine distance
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=EMBEDDING_DIM, 
                distance=Distance.COSINE
            ),
        )
        
        # Create keyword index on bot_id for O(log n) filter performance
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="bot_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        
        print(f"Created Qdrant collection: {COLLECTION_NAME}")
    else:
        print(f"Qdrant collection already exists: {COLLECTION_NAME}")


def get_qdrant_store() -> QdrantVectorStore:
    """Get Qdrant vector store for LlamaIndex with async support."""
    return QdrantVectorStore(
        client=get_qdrant_client(),
        aclient=AsyncQdrantClient(url=settings.QDRANT_URL),
        collection_name=COLLECTION_NAME,
    )


async def check_qdrant_health() -> str:
    """Check Qdrant connectivity."""
    try:
        client = get_qdrant_client()
        client.get_collections()
        return "healthy"
    except Exception:
        return "unhealthy"
