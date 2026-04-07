"""Chat router with SSE streaming."""
import logging
import time
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.models import ChatRequest
from app.services.retriever import retrieve_with_threshold
from app.services.chat_engine import stream_chat_response
from app.db.stats_repo import get_bot_record
from app.utils.errors import BotNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat")
async def chat(request: ChatRequest, req: Request):
    """
    Chat with a bot (Server-Sent Events streaming).
    
    Streams response tokens as they are generated.
    Final message includes token counts, cost, and latency.
    """
    client_ip = req.client.host if req.client else None
    logger.info(f"[CHAT] New chat request | bot_id={request.bot_id[:8]}... | client={client_ip} | message='{request.user_message[:50]}...'")
    
    # Verify bot exists
    logger.info(f"[CHAT] Step 1/3: Verifying bot exists in database...")
    if not await get_bot_record(request.bot_id):
        logger.warning(f"[CHAT] Bot not found | bot_id={request.bot_id[:8]}...")
        raise HTTPException(404, f"No knowledge base found for bot_id: {request.bot_id}")
    logger.info(f"[CHAT]   Bot verified")
    
    # Start timing
    t_start = time.monotonic()
    
    # Retrieve relevant context with threshold gating
    logger.info(f"[CHAT] Step 2/3: Retrieving relevant context...")
    retrieval = await retrieve_with_threshold(
        bot_id=request.bot_id,
        query=request.user_message,
    )
    
    if retrieval.is_answerable:
        logger.info(f"[CHAT]   Context retrieved: {len(retrieval.nodes)} nodes, max_similarity={retrieval.max_similarity:.3f} -> WILL ANSWER")
    else:
        logger.info(f"[CHAT]   Context retrieved: {len(retrieval.nodes)} nodes, max_similarity={retrieval.max_similarity:.3f} -> UNANSWERABLE (below threshold)")
    
    # Return streaming response
    logger.info(f"[CHAT] Step 3/3: Starting streaming response...")
    return StreamingResponse(
        stream_chat_response(
            bot_id=request.bot_id,
            user_message=request.user_message,
            conversation_history=[msg.model_dump() for msg in request.conversation_history] if request.conversation_history else [],
            retrieval_result=retrieval,
            t_start=t_start,
        ),
        media_type="text/event-stream",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
