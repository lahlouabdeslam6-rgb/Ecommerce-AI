from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.sqlite import get_sqlite_session
from app.repositories.marketing import MarketingRepository
from app.schemas.marketing import ActivePromotionResponse
from app.services.product import ProductService


router = APIRouter(prefix="/marketing/promotions", tags=["Promotions"])


@router.get("/active", response_model=ActivePromotionResponse | None)
async def active_promotion(
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> ActivePromotionResponse | None:
    campaign = await MarketingRepository(session).latest_active_promotion(
        now=datetime.now(UTC)
    )
    if campaign is None:
        return None
    product_ids = campaign.product_ids or (
        [campaign.product_id] if campaign.product_id else []
    )
    products = await ProductService().get_products(product_ids)
    products = [
        product
        for product in products
        if product.is_active and product.stock > 0 and product.price
    ]
    minimum = 2 if campaign.promotion_kind == "pack" else 1
    if len(products) < minimum:
        return None
    regular_total = round(
        sum(float(product.price or 0) for product in products),
        2,
    )
    discount = float(campaign.discount_percentage or 0)
    return ActivePromotionResponse(
        id=campaign.id,
        promotion_kind=campaign.promotion_kind or "single_product",
        title=campaign.campaign_title,
        headline=campaign.headline,
        message=campaign.core_message,
        cta_label=campaign.cta_label,
        products=products,
        regular_total=regular_total,
        discount_percentage=discount,
        promotional_total=round(
            regular_total * (1 - discount / 100),
            2,
        ),
        currency=products[0].currency,
        starts_at=campaign.starts_at,
        ends_at=campaign.ends_at,
    )
