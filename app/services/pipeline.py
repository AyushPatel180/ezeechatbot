"""LlamaIndex IngestionPipeline for document processing."""
import logging
from dataclasses import dataclass
from typing import List

from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document
from llama_index.core import VectorStoreIndex, StorageContext

from app.core.qdrant_client import get_qdrant_store
from app.services.cost_tracker import count_tokens

logger = logging.getLogger(__name__)

# Chunking constants
CHUNK_SIZE = 400       # Optimal for text-embedding-3-small (performs best under 512)
CHUNK_OVERLAP = 50     # ~12.5% redundancy prevents context loss at boundaries
MIN_CHUNK_CHARS = 20   # Keep short-but-meaningful policies/FAQs that are common in assessments


@dataclass
class IngestionResult:
    """Result of document ingestion."""
    node_count: int
    token_count: int


async def ingest_documents(bot_id: str, documents: List[Document]) -> IngestionResult:
    """
    Ingest documents through LlamaIndex pipeline.
    
    Three-pass strategy:
      Pass 1: SentenceSplitter respects sentence boundaries, paragraph breaks, section headers
      Pass 2: Metadata injection (bot_id for tenant isolation)
      Pass 3: Batch embedding (100 nodes per call via OpenAIEmbedding)
    
    Args:
        bot_id: Tenant identifier
        documents: List of LlamaIndex Documents
        
    Returns:
        IngestionResult with node count and token count
    """
    logger.info(f"[INGEST] Starting ingestion for bot_id={bot_id[:8]}... with {len(documents)} documents")
    
    # Inject bot_id into all documents (propagates to child nodes)
    logger.info(f"[INGEST] Step 1/5: Injecting bot_id metadata into documents")
    for i, doc in enumerate(documents):
        doc.metadata["bot_id"] = bot_id
        doc.excluded_embed_metadata_keys = ["bot_id"]  # Don't dilute embedding with UUIDs
        doc.excluded_llm_metadata_keys = []
        logger.debug(f"[INGEST]   Document {i+1}: text_length={len(doc.text)}, metadata_keys={list(doc.metadata.keys())}")
    
    # Filter out very short documents
    logger.info(f"[INGEST] Step 2/5: Filtering documents (min_chars={MIN_CHUNK_CHARS})")
    original_count = len(documents)
    documents = [d for d in documents if len(d.text.strip()) >= MIN_CHUNK_CHARS]
    filtered_count = len(documents)
    logger.info(f"[INGEST]   Filtered: {original_count} -> {filtered_count} documents")
    
    if not documents:
        logger.warning(f"[INGEST] No documents remaining after filtering")
        return IngestionResult(node_count=0, token_count=0)
    
    # Get vector store and create index for proper upsert
    logger.info(f"[INGEST] Step 3/5: Initializing vector store and index")
    vector_store = get_qdrant_store()
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex([], storage_context=storage_context)
    logger.info(f"[INGEST]   Vector store ready")
    
    # Create ingestion pipeline with SentenceSplitter
    logger.info(f"[INGEST] Step 4/5: Running ingestion pipeline (chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    pipeline = IngestionPipeline(
        transformations=[
            SentenceSplitter(
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
                paragraph_separator="\n\n",
                secondary_chunking_regex="[^,.;。？！]+[,.;。？！]?",
            ),
        ],
    )
    
    # Run async pipeline: split → batch embed
    nodes = await pipeline.arun(documents=documents, show_progress=False)
    logger.info(f"[INGEST]   Pipeline complete: created {len(nodes)} nodes from {len(documents)} documents")
    
    # Upsert nodes to Qdrant using the index
    logger.info(f"[INGEST] Step 5/5: Upserting {len(nodes)} nodes to Qdrant")
    index.insert_nodes(nodes)
    logger.info(f"[INGEST]   Upsert complete - bot_id={bot_id[:8]}... now has {len(nodes)} indexed chunks")
    
    # Calculate total tokens
    token_count = sum(count_tokens(n.text) for n in nodes)
    logger.info(f"[INGEST] Complete: {len(nodes)} chunks, {token_count} total tokens")
    
    return IngestionResult(
        node_count=len(nodes),
        token_count=token_count,
    )
