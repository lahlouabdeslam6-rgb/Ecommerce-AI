import asyncio

from fastapi import HTTPException, status

from app.core.config import settings
from app.db.ai_infrastructure import (
    check_ollama,
    check_qdrant,
    check_redis,
    get_ai_http_client,
    get_redis_client,
)
from app.schemas.ai import AIInfrastructureStatus, AIInfrastructureTestResponse


class AIInfrastructureService:
    @staticmethod
    def _model_is_installed(required: str, installed: list[str]) -> bool:
        required_name = required if ":" in required else f"{required}:latest"
        return required_name in installed

    async def status(self) -> AIInfrastructureStatus:
        redis_ready, qdrant_ready, ollama_ready = await asyncio.gather(
            check_redis(),
            check_qdrant(),
            check_ollama(),
        )
        installed_models = await self._installed_models() if ollama_ready else []
        return AIInfrastructureStatus(
            redis="healthy" if redis_ready else "unhealthy",
            qdrant="healthy" if qdrant_ready else "unhealthy",
            ollama="healthy" if ollama_ready else "unhealthy",
            chat_model=settings.ollama_chat_model,
            embedding_model=settings.ollama_embedding_model,
            installed_models=installed_models,
            models_ready=all(
                self._model_is_installed(model, installed_models)
                for model in (
                    settings.ollama_chat_model,
                    settings.ollama_embedding_model,
                )
            ),
        )

    async def run_test(self) -> AIInfrastructureTestResponse:
        current_status = await self.status()
        unavailable = [
            name
            for name in ("redis", "qdrant", "ollama")
            if getattr(current_status, name) != "healthy"
        ]
        if unavailable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                f"Unavailable AI services: {', '.join(unavailable)}",
            )
        if not current_status.models_ready:
            missing = sorted(
                model
                for model in (
                    settings.ollama_chat_model,
                    settings.ollama_embedding_model,
                )
                if not self._model_is_installed(
                    model,
                    current_status.installed_models,
                )
            )
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Missing Ollama models: {', '.join(missing)}",
            )

        redis = get_redis_client()
        cache_key = "nutrifit:ai:infrastructure-test"
        await redis.set(cache_key, "ready", ex=60)
        redis_cache_ready = await redis.get(cache_key) == "ready"

        http = get_ai_http_client()
        embedding_response = await http.post(
            f"{settings.ollama_url}/api/embed",
            json={
                "model": settings.ollama_embedding_model,
                "input": "NUTRIFIT sports nutrition product",
            },
            timeout=120,
        )
        embedding_response.raise_for_status()
        embeddings = embedding_response.json().get("embeddings") or []
        if not embeddings or not embeddings[0]:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Ollama returned no embedding",
            )
        dimensions = len(embeddings[0])
        collection_ready = await self._ensure_collection(dimensions)

        generation_response = await http.post(
            f"{settings.ollama_url}/api/generate",
            json={
                "model": settings.ollama_chat_model,
                "prompt": "Reply with exactly: NUTRIFIT AI READY",
                "stream": False,
                "options": {"temperature": 0, "num_predict": 20},
            },
            timeout=180,
        )
        generation_response.raise_for_status()
        generation = str(generation_response.json().get("response") or "").strip()
        if not generation:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Ollama returned an empty generation",
            )

        return AIInfrastructureTestResponse(
            redis_cache=redis_cache_ready,
            embedding_dimensions=dimensions,
            qdrant_collection=settings.qdrant_collection,
            qdrant_collection_ready=collection_ready,
            generation=generation,
        )

    async def _installed_models(self) -> list[str]:
        response = await get_ai_http_client().get(
            f"{settings.ollama_url}/api/tags",
            timeout=10,
        )
        response.raise_for_status()
        return sorted(
            str(item.get("name") or item.get("model"))
            for item in response.json().get("models", [])
            if item.get("name") or item.get("model")
        )

    async def _ensure_collection(self, dimensions: int) -> bool:
        http = get_ai_http_client()
        collection_url = (
            f"{settings.qdrant_url}/collections/{settings.qdrant_collection}"
        )
        response = await http.get(collection_url, timeout=10)
        if response.status_code == 404:
            response = await http.put(
                collection_url,
                json={
                    "vectors": {
                        "size": dimensions,
                        "distance": "Cosine",
                    }
                },
                timeout=30,
            )
            response.raise_for_status()
            return True
        response.raise_for_status()
        vector_config = (
            response.json()
            .get("result", {})
            .get("config", {})
            .get("params", {})
            .get("vectors", {})
        )
        configured_size = vector_config.get("size")
        if configured_size is not None and int(configured_size) != dimensions:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Qdrant collection vector size does not match the embedding model",
            )
        return True
