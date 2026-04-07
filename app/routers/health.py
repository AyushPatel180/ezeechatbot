"""Health check router."""
import logging
import httpx
from fastapi import APIRouter, HTTPException

from app.core.qdrant_client import check_qdrant_health
from app.db.database import check_db_health
from app.config import settings
from app.models import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Check health of all service dependencies.
    
    Returns status of API, Qdrant, LiteLLM Proxy, and SQLite.
    """
    logger.debug("[HEALTH] Health check requested")
    
    # Check all dependencies
    logger.info("[HEALTH] Checking dependencies: Qdrant, SQLite, LiteLLM Proxy...")
    qdrant_status = await check_qdrant_health()
    sqlite_status = await check_db_health()
    litellm_status = await check_litellm_proxy_health()
    
    logger.info(f"[HEALTH] Qdrant: {qdrant_status}, SQLite: {sqlite_status}, LiteLLM: {litellm_status}")
    
    health = HealthResponse(
        api="healthy",
        qdrant=qdrant_status,
        litellm_proxy=litellm_status,
        sqlite=sqlite_status,
    )
    
    # Return 503 if any critical dependency is unhealthy
    all_healthy = all([
        qdrant_status == "healthy",
        sqlite_status == "healthy",
        litellm_status == "healthy",
    ])
    
    if not all_healthy:
        logger.warning(f"[HEALTH] FAILED - Qdrant={qdrant_status}, SQLite={sqlite_status}, LiteLLM={litellm_status}")
        raise HTTPException(
            status_code=503,
            detail=health.model_dump()
        )
    
    logger.info("[HEALTH] All services healthy")
    return health


async def check_litellm_proxy_health() -> str:
    """Check LiteLLM Proxy connectivity."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.LITELLM_PROXY_URL}/health")
            return "healthy" if resp.status_code == 200 else "unhealthy"
    except Exception:
        return "unhealthy"
