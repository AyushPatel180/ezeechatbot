"""Stats router for bot metrics."""
from fastapi import APIRouter, HTTPException

from app.db.stats_repo import get_stats
from app.models import StatsResponse


router = APIRouter()


@router.get("/stats/{bot_id}", response_model=StatsResponse)
async def get_bot_stats(bot_id: str):
    """
    Get statistics for a bot.
    
    Returns:
    - total_messages_served
    - average_response_latency_ms
    - estimated_token_cost_usd
    - unanswered_questions
    - answerable_rate_pct
    """
    stats = await get_stats(bot_id)
    
    if stats is None:
        raise HTTPException(404, f"No knowledge base found for bot_id: {bot_id}")
    
    return StatsResponse(**stats)
