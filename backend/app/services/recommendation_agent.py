from __future__ import annotations

import json
import logging
import re
import unicodedata
from hashlib import sha256
from typing import Any

import httpx
from fastapi import HTTPException, status
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.ai_infrastructure import (
    get_ai_http_client,
    get_redis_client,
)
from app.repositories.cart import CartRepository
from app.repositories.order import OrderRepository
from app.repositories.product import ProductRepository
from app.schemas.product import ProductResponse
from app.schemas.recommendation import (
    RecommendationItem,
    RecommendationResponse,
)


logger = logging.getLogger("nutrifit.recommendation_agent")
CACHE_VERSION = "v5"
DISCLAIMER = (
    "Suggestions informatives basees sur le catalogue, pas un avis medical "
    "ni une recommandation de dosage."
)
STOP_WORDS = {
    "avec",
    "dans",
    "des",
    "les",
    "pour",
    "produit",
    "produits",
    "sans",
    "une",
    "votre",
}
SENSITIVE_AUDIENCE_TERMS = {
    "allaitement",
    "baby",
    "bebe",
    "breastfeeding",
    "child",
    "children",
    "enceinte",
    "grossesse",
    "infant",
    "kids",
    "maternal",
    "maternity",
    "prenatal",
}
OBJECTIVE_TERMS = {
    "proteines": {
        "casein",
        "caseine",
        "isolate",
        "protein",
        "proteine",
        "proteines",
        "whey",
    },
    "prise de masse": {
        "calorie",
        "calories",
        "gain",
        "gainer",
        "mass",
        "protein",
        "proteine",
        "whey",
    },
    "energie": {
        "cafeine",
        "caffeine",
        "energy",
        "energie",
        "hydration",
        "pre",
        "workout",
    },
    "recuperation": {
        "amino",
        "bcaa",
        "creatine",
        "eaa",
        "magnesium",
        "omega",
        "recovery",
        "recuperation",
    },
    "bien-etre": {
        "health",
        "magnesium",
        "mineral",
        "minerals",
        "mineraux",
        "multivitamin",
        "omega",
        "vitamin",
        "vitamine",
        "vitamines",
        "wellness",
        "zinc",
    },
}


class RecommendationAgentService:
    def __init__(
        self,
        session: AsyncSession | None = None,
        product_repository: ProductRepository | None = None,
    ) -> None:
        self.session = session
        self.products = product_repository or ProductRepository()

    async def for_product(
        self,
        product_id: int,
        *,
        limit: int,
    ) -> RecommendationResponse:
        source = await self.products.get_by_product_id(product_id)
        if source is None or not source.get("is_active"):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "Product not found",
            )
        cache_key = self._cache_key(
            "product",
            {
                "product_id": product_id,
                "updated_at": str(source.get("updated_at") or ""),
                "limit": limit,
            },
        )
        cached = await self._cache_get(cache_key)
        if cached:
            return RecommendationResponse.model_validate_json(cached)

        result = await self._recommend(
            context="product",
            source_products=[source],
            exclude_ids=[product_id],
            objective=None,
            max_price=None,
            limit=limit,
            personalized=False,
        )
        await self._cache_set(cache_key, result.model_dump_json(), ttl=300)
        return result

    async def for_cart(
        self,
        user_id: int,
        *,
        objective: str | None,
        max_price: float | None,
        limit: int,
    ) -> RecommendationResponse:
        if self.session is None:
            raise RuntimeError("A SQLite session is required for cart context")
        cart_ids = [
            item.product_id
            for item in await CartRepository(self.session).list_items(user_id)
        ]
        order_ids = await OrderRepository(self.session).recent_product_ids(
            user_id,
            limit=30,
        )
        source_ids = self._unique_ints([*cart_ids, *order_ids])[:30]
        source_map = await self.products.get_many_by_ids(source_ids)
        source_products = [
            source_map[product_id]
            for product_id in source_ids
            if product_id in source_map
        ]
        cache_key = self._cache_key(
            "cart",
            {
                "user_id": user_id,
                "source_ids": source_ids,
                "objective": objective,
                "max_price": max_price,
                "limit": limit,
            },
        )
        cached = await self._cache_get(cache_key)
        if cached:
            return RecommendationResponse.model_validate_json(cached)

        result = await self._recommend(
            context="cart",
            source_products=source_products,
            exclude_ids=source_ids,
            objective=objective,
            max_price=max_price,
            limit=limit,
            personalized=bool(source_products or objective),
        )
        await self._cache_set(cache_key, result.model_dump_json(), ttl=180)
        return result

    async def _recommend(
        self,
        *,
        context: str,
        source_products: list[dict[str, Any]],
        exclude_ids: list[int],
        objective: str | None,
        max_price: float | None,
        limit: int,
        personalized: bool,
    ) -> RecommendationResponse:
        candidates = await self.products.recommendation_candidates(
            exclude_ids=exclude_ids,
            max_price=max_price,
            limit=500,
        )
        query_text = " | ".join(
            item
            for item in (
                objective or "",
                *(self._product_text(product) for product in source_products[:8]),
            )
            if item
        )
        context_terms = self._tokens(query_text)
        candidates = [
            candidate
            for candidate in candidates
            if self._audience_is_compatible(
                candidate,
                context_terms=context_terms,
            )
        ]
        objective_terms = self._objective_terms(objective or "")
        if objective_terms:
            objective_matches = [
                candidate
                for candidate in candidates
                if self._objective_product_terms(candidate) & objective_terms
            ]
            if objective_matches:
                candidates = objective_matches
        semantic_scores = (
            await self._semantic_scores(
                query_text,
                exclude_ids=exclude_ids,
                max_price=max_price,
                limit=max(limit * 8, 32),
            )
            if query_text
            else {}
        )
        ranked = [
            self._score_candidate(
                candidate,
                source_products=source_products,
                objective=objective,
                max_price=max_price,
                semantic_score=semantic_scores.get(
                    int(candidate["product_id"])
                ),
            )
            for candidate in candidates
        ]
        ranked.sort(
            key=lambda item: (
                -item[0],
                int(item[2].get("product_id") or 0),
            )
        )
        items = [
            RecommendationItem(
                product=ProductResponse.model_validate(product),
                score=round(score, 3),
                reasons=reasons[:4],
            )
            for score, reasons, product in ranked[:limit]
        ]
        return RecommendationResponse(
            context=context,
            strategy=(
                "semantic+catalogue" if semantic_scores else "catalogue"
            ),
            personalized=personalized,
            items=items,
            disclaimer=DISCLAIMER,
        )

    @classmethod
    def _score_candidate(
        cls,
        candidate: dict[str, Any],
        *,
        source_products: list[dict[str, Any]],
        objective: str | None,
        max_price: float | None,
        semantic_score: float | None,
    ) -> tuple[float, list[str], dict[str, Any]]:
        score = max(float(semantic_score or 0), 0) * 4
        reasons: list[str] = []
        candidate_category = cls._normalize(candidate.get("category"))
        candidate_brand = cls._normalize(candidate.get("brand"))
        candidate_terms = cls._product_terms(candidate)

        source_categories = {
            cls._normalize(product.get("category"))
            for product in source_products
            if product.get("category")
        }
        source_brands = {
            cls._normalize(product.get("brand"))
            for product in source_products
            if product.get("brand")
        }
        source_terms: set[str] = set()
        for product in source_products:
            source_terms.update(cls._product_terms(product))

        if candidate_category and candidate_category in source_categories:
            score += 3
            reasons.append(
                f"Meme categorie: {candidate.get('category')}"
            )
        if candidate_brand and candidate_brand in source_brands:
            score += 0.75
            reasons.append("Marque deja presente dans votre selection")

        shared_terms = sorted(candidate_terms & source_terms)
        if shared_terms:
            score += min(len(shared_terms) * 0.35, 2.1)
            reasons.append("Profil nutritionnel proche")

        objective_terms = cls._objective_terms(objective or "")
        matching_objective = sorted(
            cls._objective_product_terms(candidate) & objective_terms
        )
        if matching_objective:
            score += min(len(matching_objective) * 1.6, 6.4)
            reasons.append("Correspond aux mots-cles de votre objectif")

        candidate_price = float(candidate.get("price") or 0)
        if max_price is not None and candidate_price <= max_price:
            score += 0.5
            reasons.append(f"Dans votre budget de {max_price:g} MAD")

        stock = int(candidate.get("stock") or 0)
        score += min(stock, 20) / 100
        if semantic_score is not None and semantic_score > 0.35:
            reasons.insert(0, "Profil semantique pertinent")
        if not reasons:
            reasons.append("Disponible actuellement")
        return score, cls._unique_strings(reasons), candidate

    async def _semantic_scores(
        self,
        query_text: str,
        *,
        exclude_ids: list[int],
        max_price: float | None,
        limit: int,
    ) -> dict[int, float]:
        try:
            client = get_ai_http_client()
            embedding_response = await client.post(
                f"{settings.ollama_url}/api/embed",
                json={
                    "model": settings.ollama_embedding_model,
                    "input": query_text[:12000],
                },
                timeout=120,
            )
            embedding_response.raise_for_status()
            embeddings = embedding_response.json().get("embeddings") or []
            if not embeddings or not embeddings[0]:
                return {}
            must: list[dict[str, Any]] = [
                {"key": "is_active", "match": {"value": True}},
                {"key": "stock", "range": {"gt": 0}},
            ]
            if max_price is not None:
                must.append(
                    {"key": "price", "range": {"lte": max_price}}
                )
            query_response = await client.post(
                (
                    f"{settings.qdrant_url}/collections/"
                    f"{settings.qdrant_collection}/points/query"
                ),
                json={
                    "query": embeddings[0],
                    "filter": {"must": must},
                    "limit": limit,
                    "with_payload": True,
                },
                timeout=30,
            )
            query_response.raise_for_status()
            raw_result = query_response.json().get("result") or {}
            points = (
                raw_result.get("points", [])
                if isinstance(raw_result, dict)
                else raw_result
            )
            excluded = set(exclude_ids)
            scores: dict[int, float] = {}
            for point in points:
                payload = point.get("payload") or {}
                product_id = int(
                    payload.get("product_id") or point.get("id")
                )
                if product_id not in excluded:
                    scores[product_id] = float(point.get("score") or 0)
            return scores
        except (
            httpx.HTTPError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            logger.info("Recommendation semantic fallback: %s", exc)
            return {}

    @classmethod
    def _product_text(cls, product: dict[str, Any]) -> str:
        ingredients = [
            str(item.get("name"))
            for item in product.get("ingredients") or []
            if isinstance(item, dict) and item.get("name")
        ]
        return " | ".join(
            str(value)
            for value in (
                product.get("name"),
                product.get("brand"),
                product.get("category"),
                product.get("description"),
                ", ".join(ingredients),
                ", ".join(product.get("tags") or []),
            )
            if value
        )

    @classmethod
    def _product_terms(cls, product: dict[str, Any]) -> set[str]:
        return cls._tokens(cls._product_text(product))

    @classmethod
    def _objective_product_terms(
        cls,
        product: dict[str, Any],
    ) -> set[str]:
        identity_text = " | ".join(
            str(value)
            for value in (
                product.get("name"),
                product.get("description"),
                ", ".join(product.get("tags") or []),
                ", ".join(product.get("seo_keywords") or []),
            )
            if value
        )
        return cls._tokens(identity_text)

    @classmethod
    def _audience_is_compatible(
        cls,
        product: dict[str, Any],
        *,
        context_terms: set[str],
    ) -> bool:
        sensitive_product_terms = (
            cls._product_terms(product) & SENSITIVE_AUDIENCE_TERMS
        )
        if not sensitive_product_terms:
            return True
        return bool(context_terms & sensitive_product_terms)

    @classmethod
    def _tokens(cls, value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", cls._normalize(value))
            if len(token) >= 3 and token not in STOP_WORDS
        }

    @classmethod
    def _objective_terms(cls, value: str) -> set[str]:
        normalized = cls._normalize(value)
        terms = cls._tokens(normalized)
        for objective, aliases in OBJECTIVE_TERMS.items():
            if objective in normalized:
                terms.update(aliases)
        return terms

    @staticmethod
    def _normalize(value: Any) -> str:
        normalized = unicodedata.normalize("NFKD", str(value or ""))
        normalized = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )
        return re.sub(r"\s+", " ", normalized).strip().lower()

    @staticmethod
    def _unique_ints(values: list[int]) -> list[int]:
        result: list[int] = []
        for value in values:
            parsed = int(value)
            if parsed not in result:
                result.append(parsed)
        return result

    @staticmethod
    def _unique_strings(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value))

    @staticmethod
    def _cache_key(context: str, payload: dict[str, Any]) -> str:
        fingerprint = sha256(
            json.dumps(
                payload,
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:24]
        return (
            f"nutrifit:recommendation:{CACHE_VERSION}:"
            f"{context}:{fingerprint}"
        )

    @staticmethod
    async def _cache_get(key: str) -> str | None:
        try:
            return await get_redis_client().get(key)
        except (RuntimeError, RedisError):
            return None

    @staticmethod
    async def _cache_set(key: str, value: str, *, ttl: int) -> None:
        try:
            await get_redis_client().set(key, value, ex=ttl)
        except (RuntimeError, RedisError):
            return
