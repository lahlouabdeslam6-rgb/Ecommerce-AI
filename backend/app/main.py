from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator

import asyncio
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.admin import router as admin_router
from app.api.analytics import router as analytics_router
from app.api.ai import router as ai_router
from app.api.auth import router as auth_router
from app.api.cart import router as cart_router
from app.api.content import router as content_router
from app.api.marketing import router as marketing_router
from app.api.safety import router as safety_router
from app.api.orders import router as orders_router
from app.api.operations import router as operations_router
from app.api.products import router as products_router
from app.api.recommendations import router as recommendations_router
from app.api.support import router as support_router
from app.api.orchestrator import router as orchestrator_router
from app.api.tickets import router as tickets_router
from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.core.security import require_roles
from app.models.user import User
from app.db.mongodb import check_mongodb, connect_mongodb, disconnect_mongodb
from app.db.ai_infrastructure import (
    check_ollama,
    check_qdrant,
    check_redis,
    connect_ai_infrastructure,
    disconnect_ai_infrastructure,
)
from app.db.sqlite import check_sqlite, disconnect_sqlite, initialize_sqlite
from app.repositories.product import ProductRepository


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await connect_mongodb()
    await connect_ai_infrastructure()
    await initialize_sqlite()
    await ProductRepository().ensure_indexes()
    try:
        yield
    finally:
        await disconnect_mongodb()
        await disconnect_ai_infrastructure()
        await disconnect_sqlite()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("nutrifit.api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

RATE_LIMITED_PATHS: dict[str, tuple[int, int]] = {
    "/api/auth/login": (10, 60),
    "/api/auth/register": (5, 300),
    "/api/auth/forgot-password": (5, 300),
    "/api/auth/reset-password": (5, 300),
}
STARTED_AT = perf_counter()
REQUEST_METRICS = {"requests": 0, "errors": 0, "total_duration_ms": 0.0}


@app.middleware("http")
async def security_and_observability(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    started_at = perf_counter()
    client_ip = request.client.host if request.client else "unknown"
    limit_config = RATE_LIMITED_PATHS.get(request.url.path)
    if request.method == "POST" and (
        "/tickets" in request.url.path or request.url.path.endswith("/messages")
    ):
        limit_config = (20, 300)
    if limit_config and not rate_limiter.allow(
        f"{client_ip}:{request.url.path}",
        limit=limit_config[0],
        window_seconds=limit_config[1],
    ):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Too many requests. Try again later."},
            headers={"X-Request-ID": request_id, "Retry-After": "60"},
        )
    response = await call_next(request)
    duration_ms = round((perf_counter() - started_at) * 1000, 2)
    REQUEST_METRICS["requests"] += 1
    REQUEST_METRICS["total_duration_ms"] += duration_ms
    if response.status_code >= 500:
        REQUEST_METRICS["errors"] += 1
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = str(duration_ms)
    logger.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response

app.include_router(products_router, prefix="/api")
app.include_router(recommendations_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(cart_router, prefix="/api")
app.include_router(content_router, prefix="/api")
app.include_router(marketing_router, prefix="/api")
app.include_router(safety_router, prefix="/api")
app.include_router(orders_router, prefix="/api")
app.include_router(operations_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(tickets_router, prefix="/api")
app.include_router(support_router, prefix="/api")
app.include_router(orchestrator_router, prefix="/api")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", tags=["System"])
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "message": "NUTRIFIT API is running",
    }


@app.get("/health", tags=["System"])
async def health(response: Response) -> dict[str, object]:
    services: dict[str, str] = {"api": "healthy"}

    try:
        services["mongodb"] = "healthy" if await check_mongodb() else "unhealthy"
    except Exception:
        services["mongodb"] = "unhealthy"

    try:
        services["sqlite"] = "healthy" if await check_sqlite() else "unhealthy"
    except Exception:
        services["sqlite"] = "unhealthy"

    ai_checks = await asyncio.gather(
        check_redis(),
        check_qdrant(),
        check_ollama(),
        return_exceptions=True,
    )
    for name, result in zip(("redis", "qdrant", "ollama"), ai_checks):
        services[name] = "healthy" if result is True else "unhealthy"

    overall_status = (
        "healthy"
        if all(service == "healthy" for service in services.values())
        else "unhealthy"
    )
    if overall_status == "unhealthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": overall_status, "services": services}


@app.get("/api/admin/metrics", tags=["System"])
async def metrics(
    _: Annotated[User, Depends(require_roles("admin"))],
) -> dict[str, object]:
    request_count = int(REQUEST_METRICS["requests"])
    return {
        "uptime_seconds": round(perf_counter() - STARTED_AT, 2),
        "requests": request_count,
        "server_errors": int(REQUEST_METRICS["errors"]),
        "average_response_ms": round(
            float(REQUEST_METRICS["total_duration_ms"]) / max(request_count, 1),
            2,
        ),
        "version": settings.app_version,
    }
