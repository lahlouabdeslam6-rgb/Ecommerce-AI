import httpx
from redis.asyncio import Redis

from app.core.config import settings


redis_client: Redis | None = None
ai_http_client: httpx.AsyncClient | None = None


async def connect_ai_infrastructure() -> None:
    global redis_client, ai_http_client
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    ai_http_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0))


async def disconnect_ai_infrastructure() -> None:
    global redis_client, ai_http_client
    if redis_client is not None:
        await redis_client.aclose()
    if ai_http_client is not None:
        await ai_http_client.aclose()
    redis_client = None
    ai_http_client = None


def get_redis_client() -> Redis:
    if redis_client is None:
        raise RuntimeError("Redis is not initialized")
    return redis_client


def get_ai_http_client() -> httpx.AsyncClient:
    if ai_http_client is None:
        raise RuntimeError("AI HTTP client is not initialized")
    return ai_http_client


async def check_redis() -> bool:
    try:
        return bool(await get_redis_client().ping())
    except Exception:
        return False


async def check_qdrant() -> bool:
    try:
        response = await get_ai_http_client().get(
            f"{settings.qdrant_url}/collections",
            timeout=5,
        )
        return response.status_code == 200
    except Exception:
        return False


async def check_ollama() -> bool:
    try:
        response = await get_ai_http_client().get(
            f"{settings.ollama_url}/api/tags",
            timeout=5,
        )
        return response.status_code == 200
    except Exception:
        return False
