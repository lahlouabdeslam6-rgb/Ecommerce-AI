from typing import Annotated

from fastapi import APIRouter, Depends, Query
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
)
from app.services.marketing_agent import MarketingAgentService


router = APIRouter(prefix="/admin/ai/marketing", tags=["AI Marketing"])


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
    "/campaigns/{campaign_id}/approve",
    response_model=MarketingCampaignResponse,
)
async def approve_campaign(
    campaign_id: int,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> MarketingCampaignResponse:
    campaign = await MarketingAgentService(session).approve(
        campaign_id,
        approved_by=admin.id,
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
