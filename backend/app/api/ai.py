from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.repositories.operations import OperationsRepository
from app.schemas.ai import (
    AIInfrastructureStatus,
    AIInfrastructureTestResponse,
    ProductAIApplyResponse,
    ProductAISuggestion,
    ProductAISuggestionResponse,
)
from app.services.ai_infrastructure import AIInfrastructureService
from app.services.product_agent import ProductAgentService
from app.services.safety_agent import SafetyAgentService


router = APIRouter(prefix="/admin/ai", tags=["AI Infrastructure"])


@router.get("/status", response_model=AIInfrastructureStatus)
async def ai_infrastructure_status(
    _: Annotated[User, Depends(require_roles("admin"))],
) -> AIInfrastructureStatus:
    return await AIInfrastructureService().status()


@router.post("/test", response_model=AIInfrastructureTestResponse)
async def test_ai_infrastructure(
    _: Annotated[User, Depends(require_roles("admin"))],
) -> AIInfrastructureTestResponse:
    return await AIInfrastructureService().run_test()


@router.post(
    "/products/{product_id}/suggest",
    response_model=ProductAISuggestionResponse,
)
async def suggest_product_content(
    product_id: int,
    user: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> ProductAISuggestionResponse:
    result = await ProductAgentService().suggest(product_id)
    OperationsRepository(session).add_audit(
        actor_id=user.id,
        actor_role=user.role,
        action="ai.product.suggest",
        entity_type="product",
        entity_id=product_id,
        details={"model": result.model, "cached": result.cached},
    )
    await session.commit()
    return result


@router.post(
    "/products/{product_id}/apply",
    response_model=ProductAIApplyResponse,
)
async def apply_product_content(
    product_id: int,
    suggestion: ProductAISuggestion,
    user: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> ProductAIApplyResponse:
    safety_text = "\n".join(
        [
            suggestion.description,
            suggestion.seo_title,
            suggestion.seo_description,
            " ".join(suggestion.seo_keywords),
            " ".join(suggestion.tags),
        ]
    )
    await SafetyAgentService(session).enforce(
        safety_text,
        source_type="product_suggestion",
        source_id=product_id,
        action="product.apply",
        actor_id=user.id,
        actor_role=user.role,
    )
    result = await ProductAgentService().apply(product_id, suggestion)
    OperationsRepository(session).add_audit(
        actor_id=user.id,
        actor_role=user.role,
        action="ai.product.apply",
        entity_type="product",
        entity_id=product_id,
        details={
            "model": result.product.ai_model,
            "indexed": result.indexed,
            "fields": [
                "description",
                "category",
                "seo_title",
                "seo_description",
                "seo_keywords",
                "tags",
            ],
        },
    )
    await session.commit()
    return result
