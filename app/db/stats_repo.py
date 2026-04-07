"""Statistics repository for bot metrics."""
import aiosqlite
from datetime import datetime, timezone
from typing import Optional
from app.config import settings


# Pricing constants for reference (fallback if LiteLLM callback fails)
INPUT_COST_PER_TOKEN = 0.15 / 1_000_000   # gpt-4.1-mini
OUTPUT_COST_PER_TOKEN = 0.60 / 1_000_000  # gpt-4.1-mini


async def create_bot_record(bot_id: str):
    """Create initial stats record for a new bot."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(settings.SQLITE_DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO bot_stats 
                (bot_id, created_at, last_active_at) 
                VALUES (?, ?, ?)""",
            (bot_id, now, now),
        )
        await db.commit()


async def get_bot_record(bot_id: str) -> Optional[bool]:
    """Check if bot exists."""
    async with aiosqlite.connect(settings.SQLITE_DB_PATH) as db:
        async with db.execute(
            "SELECT bot_id FROM bot_stats WHERE bot_id=?", (bot_id,)
        ) as cur:
            row = await cur.fetchone()
            return row is not None


async def record_interaction(
    bot_id: str, 
    latency_ms: int, 
    input_tokens: int, 
    output_tokens: int, 
    unanswered: bool = False,
    llm_cost_usd: float = 0.0
):
    """Record a chat interaction with metrics."""
    now = datetime.now(timezone.utc).isoformat()
    
    # Calculate cost if not provided by LiteLLM
    if llm_cost_usd == 0.0 and input_tokens > 0:
        llm_cost_usd = (input_tokens * INPUT_COST_PER_TOKEN + 
                       output_tokens * OUTPUT_COST_PER_TOKEN)
    
    async with aiosqlite.connect(settings.SQLITE_DB_PATH) as db:
        await db.execute("""
            UPDATE bot_stats SET
                total_messages       = total_messages + 1,
                total_latency_ms     = total_latency_ms + ?,
                total_input_tokens   = total_input_tokens + ?,
                total_output_tokens  = total_output_tokens + ?,
                total_llm_cost_usd   = total_llm_cost_usd + ?,
                unanswered_questions = unanswered_questions + ?,
                last_active_at       = ?
            WHERE bot_id = ?
        """, (latency_ms, input_tokens, output_tokens, llm_cost_usd, 
              int(unanswered), now, bot_id))
        await db.commit()


async def record_llm_cost(bot_id: str, cost_usd: float):
    """Record actual LLM cost from LiteLLM callback."""
    async with aiosqlite.connect(settings.SQLITE_DB_PATH) as db:
        await db.execute(
            "UPDATE bot_stats SET total_llm_cost_usd = total_llm_cost_usd + ? WHERE bot_id = ?",
            (cost_usd, bot_id)
        )
        await db.commit()


async def get_stats(bot_id: str) -> Optional[dict]:
    """Get comprehensive stats for a bot."""
    async with aiosqlite.connect(settings.SQLITE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM bot_stats WHERE bot_id=?", (bot_id,)
        ) as cur:
            row = await cur.fetchone()
    
    if not row:
        return None
    
    n = row["total_messages"]
    avg_latency = (row["total_latency_ms"] / n) if n > 0 else 0.0
    answerable = n - row["unanswered_questions"]
    answerable_pct = round((answerable / n * 100), 1) if n > 0 else 100.0
    
    return {
        "bot_id": bot_id,
        "total_messages_served": n,
        "average_response_latency_ms": round(avg_latency, 1),
        "estimated_token_cost_usd": round(row["total_llm_cost_usd"], 6),
        "unanswered_questions": row["unanswered_questions"],
        "answerable_rate_pct": answerable_pct,
        "created_at": row["created_at"],
        "last_active_at": row["last_active_at"],
    }
