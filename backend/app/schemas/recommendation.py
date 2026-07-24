from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.product import ProductResponse


class RecommendationItem(BaseModel):
    product: ProductResponse
    score: float = Field(ge=0)
    reasons: list[str] = Field(default_factory=list, max_length=4)


class RecommendationResponse(BaseModel):
    context: Literal["product", "cart"]
    strategy: Literal["semantic+catalogue", "catalogue"]
    personalized: bool
    items: list[RecommendationItem]
    disclaimer: str
