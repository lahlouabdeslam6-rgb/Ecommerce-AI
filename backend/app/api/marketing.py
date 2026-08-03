from pathlib import Path
from typing import Annotated
from uuid import uuid4

from anyio import to_thread
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.repositories.operations import OperationsRepository
from app.schemas.marketing import (
    MarketingCampaignListResponse,
    MarketingCampaignResponse,
    MarketingCampaignUpdate,
    MarketingGenerateRequest,
    PromotionSuggestionRequest,
    PromotionSuggestionResponse,
)
from app.services.marketing_agent import MarketingAgentService
from app.services.pack import PackService
from app.services.product import ProductService
from app.services.promotion_scoring import PromotionScoringService
from app.services.safety_agent import SafetyAgentService


router = APIRouter(prefix="/admin/ai/marketing", tags=["AI Marketing"])
PACK_COVER_DIRECTORY = Path("app/static/uploads/packs")
MAX_PACK_COVER_SIZE = 5 * 1024 * 1024
ALLOWED_PACK_COVER_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def _valid_pack_cover(extension: str, content: bytes) -> bool:
    return bool(content) and {
        "jpg": content.startswith(b"\xff\xd8\xff"),
        "png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
    }.get(extension, False)


@router.post(
    "/promotions/suggest",
    response_model=PromotionSuggestionResponse,
)
async def suggest_promotion(
    data: PromotionSuggestionRequest,
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> PromotionSuggestionResponse:
    return await PromotionScoringService(session).suggest(
        promotion_kind=data.promotion_kind,
        selection_strategy=data.selection_strategy,
        product_ids=data.product_ids or None,
    )


@router.get("/campaigns", response_model=MarketingCampaignListResponse)
async def list_campaigns(
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    campaign_type: Annotated[str | None, Query(max_length=40)] = None,
    campaign_status: Annotated[str | None, Query(max_length=20)] = None,
) -> MarketingCampaignListResponse:
    return await MarketingAgentService(session).list(
        page=page,
        page_size=page_size,
        campaign_type=campaign_type,
        campaign_status=campaign_status,
    )


@router.post(
    "/campaigns/generate",
    response_model=MarketingCampaignResponse,
)
async def generate_campaign(
    data: MarketingGenerateRequest,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> MarketingCampaignResponse:
    campaign = await MarketingAgentService(session).generate(
        data,
        created_by=admin.id,
    )
    OperationsRepository(session).add_audit(
        actor_id=admin.id,
        actor_role=admin.role,
        action="ai.marketing.generated",
        entity_type="ai_marketing_campaign",
        entity_id=campaign.id,
        details={
            "campaign_type": campaign.campaign_type,
            "channels": campaign.channels,
            "model": campaign.model,
        },
    )
    await session.commit()
    return campaign


@router.patch(
    "/campaigns/{campaign_id}",
    response_model=MarketingCampaignResponse,
)
async def update_campaign(
    campaign_id: int,
    data: MarketingCampaignUpdate,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> MarketingCampaignResponse:
    campaign = await MarketingAgentService(session).update(campaign_id, data)
    await PackService(session).deactivate_campaign_pack(campaign_id)
    OperationsRepository(session).add_audit(
        actor_id=admin.id,
        actor_role=admin.role,
        action="ai.marketing.updated",
        entity_type="ai_marketing_campaign",
        entity_id=campaign_id,
        details={"fields": sorted(data.model_fields_set)},
    )
    await session.commit()
    return campaign


@router.post(
    "/campaigns/{campaign_id}/pack-cover",
    response_model=MarketingCampaignResponse,
)
async def upload_campaign_pack_cover(
    campaign_id: int,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    file: Annotated[UploadFile, File()],
) -> MarketingCampaignResponse:
    extension = ALLOWED_PACK_COVER_TYPES.get((file.content_type or "").lower())
    content = await file.read(MAX_PACK_COVER_SIZE + 1)
    if (
        not extension
        or len(content) > MAX_PACK_COVER_SIZE
        or not _valid_pack_cover(extension, content)
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Photo invalide. JPG, PNG ou WebP, 5 MB maximum",
        )

    PACK_COVER_DIRECTORY.mkdir(parents=True, exist_ok=True)
    filename = f"campaign-{campaign_id}-pack-cover-{uuid4().hex}.{extension}"
    target = PACK_COVER_DIRECTORY / filename
    image_url = f"/static/uploads/packs/{filename}"
    try:
        await to_thread.run_sync(target.write_bytes, content)
        campaign = await MarketingAgentService(session).set_pack_cover(
            campaign_id,
            image_url,
        )
        await PackService(session).deactivate_campaign_pack(campaign_id)
        OperationsRepository(session).add_audit(
            actor_id=admin.id,
            actor_role=admin.role,
            action="ai.marketing.pack_cover_updated",
            entity_type="ai_marketing_campaign",
            entity_id=campaign_id,
            details={"image_url": image_url},
        )
        await session.commit()
        return campaign
    except Exception:
        if target.exists():
            await to_thread.run_sync(target.unlink)
        raise


@router.post(
    "/campaigns/{campaign_id}/approve",
    response_model=MarketingCampaignResponse,
)
async def approve_campaign(
    campaign_id: int,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> MarketingCampaignResponse:
    service = MarketingAgentService(session)
    draft = await service.get(campaign_id)
    selected_products = await ProductService().get_products(draft.product_ids)
    product_safety_text = "\n".join(
        " | ".join(
            [
                product.name or f"Produit #{product.product_id}",
                product.category or "",
                product.description or "",
                ", ".join(
                    ingredient.name
                    for ingredient in product.ingredients[:20]
                    if ingredient.name
                ),
            ]
        )
        for product in selected_products
    )
    safety_text = "\n".join(
        value
        for value in (
            draft.campaign_title,
            draft.headline,
            draft.core_message,
            draft.email_subject,
            draft.email_body,
            draft.whatsapp_message,
            draft.social_caption,
            draft.cta_label,
            " ".join(draft.hashtags),
            product_safety_text,
        )
        if value
    )
    await SafetyAgentService(session).enforce(
        safety_text,
        source_type="marketing_campaign",
        source_id=campaign_id,
        action="marketing.approve",
        actor_id=admin.id,
        actor_role=admin.role,
    )
    campaign = await service.approve(
        campaign_id,
        approved_by=admin.id,
    )
    pack = await PackService(session).sync_marketing_campaign(
        campaign,
        created_by=admin.id,
    )
    OperationsRepository(session).add_audit(
        actor_id=admin.id,
        actor_role=admin.role,
        action="ai.marketing.approved",
        entity_type="ai_marketing_campaign",
        entity_id=campaign_id,
        details={
            "channels": campaign.channels,
            "dispatch": "not_sent",
            "pack_id": pack.id if pack else None,
        },
    )
    await session.commit()
    return campaign


@router.post(
    "/campaigns/{campaign_id}/archive",
    response_model=MarketingCampaignResponse,
)
async def archive_campaign(
    campaign_id: int,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> MarketingCampaignResponse:
    campaign = await MarketingAgentService(session).archive(campaign_id)
    await PackService(session).deactivate_campaign_pack(campaign_id)
    OperationsRepository(session).add_audit(
        actor_id=admin.id,
        actor_role=admin.role,
        action="ai.marketing.archived",
        entity_type="ai_marketing_campaign",
        entity_id=campaign_id,
        details={"campaign_type": campaign.campaign_type},
    )
    await session.commit()
    return campaign
