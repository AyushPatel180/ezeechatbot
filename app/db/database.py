"""SQLite database setup with aiosqlite."""
import aiosqlite
from app.config import settings


async def init_db():
    """Initialize database with WAL mode for concurrent read/write safety."""
    async with aiosqlite.connect(settings.SQLITE_DB_PATH) as db:
        # Enable WAL mode for better concurrency
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")
        
        # Create bot stats table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_stats (
                bot_id                TEXT PRIMARY KEY,
                total_messages        INTEGER DEFAULT 0,
                total_latency_ms      REAL    DEFAULT 0.0,
                total_input_tokens    INTEGER DEFAULT 0,
                total_output_tokens   INTEGER DEFAULT 0,
                total_llm_cost_usd    REAL    DEFAULT 0.0,
                unanswered_questions  INTEGER DEFAULT 0,
                created_at            TEXT    NOT NULL,
                last_active_at        TEXT    NOT NULL
            )
        """)
        
        await db.commit()


async def check_db_health() -> str:
    """Check SQLite database connectivity."""
    try:
        async with aiosqlite.connect(settings.SQLITE_DB_PATH) as db:
            await db.execute("SELECT 1")
            return "healthy"
    except Exception:
        return "unhealthy"
