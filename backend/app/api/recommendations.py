from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.schemas.recommendation import RecommendationResponse
from app.services.recommendation_agent import RecommendationAgentService


router = APIRouter(prefix="/recommendations", tags=["AI Recommendations"])


@router.get(
    "/products/{product_id}",
    response_model=RecommendationResponse,
)
async def product_recommendations(
    product_id: int,
    limit: Annotated[int, Query(ge=1, le=8)] = 4,
) -> RecommendationResponse:
    return await RecommendationAgentService().for_product(
        product_id,
        limit=limit,
    )


@router.get("/cart", response_model=RecommendationResponse)
async def cart_recommendations(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    objective: Annotated[
        str | None,
        Query(min_length=2, max_length=120),
    ] = None,
    max_price: Annotated[float | None, Query(gt=0, le=100000)] = None,
    limit: Annotated[int, Query(ge=1, le=8)] = 4,
) -> RecommendationResponse:
    return await RecommendationAgentService(session).for_cart(
        user.id,
        objective=objective,
        max_price=max_price,
        limit=limit,
    )
