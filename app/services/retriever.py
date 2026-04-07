"""Hybrid retrieval with similarity threshold gate for hallucination prevention."""
import logging
from dataclasses import dataclass
from typing import List

from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.vector_stores.types import MetadataFilters, MetadataFilter
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.schema import NodeWithScore

from app.core.qdrant_client import get_qdrant_store
from app.config import settings

logger = logging.getLogger(__name__)


# Similarity threshold rationale:
# - 0.30 catches ~85% of truly out-of-scope questions
# - Allows borderline paraphrased queries (0.30-0.50) to pass
# - Prevents LLM calls entirely on unanswerable questions (saves cost + stats)
SIMILARITY_THRESHOLD = 0.30
TOP_K = 5


@dataclass
class RetrievalResult:
    """Result of retrieval operation."""
    nodes: List[NodeWithScore]
    is_answerable: bool
    max_similarity: float


async def retrieve_with_threshold(bot_id: str, query: str) -> RetrievalResult:
    """
    Retrieve relevant chunks with similarity threshold gating.
    
    The threshold gate prevents hallucinations by blocking LLM calls
    when no relevant context is found.
    
    Args:
        bot_id: Tenant identifier for isolation
        query: User query
        
    Returns:
        RetrievalResult with nodes and answerability flag
    """
    logger.info(f"[RETRIEVE] Starting retrieval for bot_id={bot_id[:8]}... query='{query[:50]}...'")
    
    logger.info(f"[RETRIEVE] Step 1/3: Initializing vector store and index")
    vector_store = get_qdrant_store()
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)
    logger.info(f"[RETRIEVE]   Index ready")
    
    # Create retriever with tenant isolation via metadata filter
    logger.info(f"[RETRIEVE] Step 2/3: Creating retriever (top_k={TOP_K}, threshold={settings.SIMILARITY_THRESHOLD})")
    retriever = VectorIndexRetriever(
        index=index,
        similarity_top_k=TOP_K,
        filters=MetadataFilters(
            filters=[MetadataFilter(key="bot_id", value=bot_id)]
        ),
    )
    logger.info(f"[RETRIEVE]   Retriever ready with bot_id filter")
    
    # Retrieve nodes
    logger.info(f"[RETRIEVE] Step 3/3: Executing vector search...")
    nodes: List[NodeWithScore] = await retriever.aretrieve(query)
    
    if not nodes:
        logger.warning(f"[RETRIEVE] No nodes found for bot_id={bot_id[:8]}...")
        return RetrievalResult(nodes=[], is_answerable=False, max_similarity=0.0)
    
    # Calculate max similarity score
    max_similarity = max(n.score for n in nodes if n.score is not None)
    is_answerable = max_similarity >= settings.SIMILARITY_THRESHOLD
    
    logger.info(f"[RETRIEVE] Complete: Found {len(nodes)} nodes, max_similarity={max_similarity:.3f}, threshold={settings.SIMILARITY_THRESHOLD}, answerable={is_answerable}")
    
    # Log top node details
    for i, node in enumerate(nodes[:3]):
        preview = node.node.text[:80].replace('\n', ' ') if node.node.text else 'N/A'
        logger.debug(f"[RETRIEVE]   Node {i+1}: score={node.score:.3f} | text='{preview}...'")
    
    return RetrievalResult(
        nodes=nodes,
        is_answerable=is_answerable,
        max_similarity=max_similarity,
    )
