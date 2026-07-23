import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_marketing import AIMarketingCampaign


class MarketingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: dict[str, Any]) -> AIMarketingCampaign:
        values = dict(data)
        channels = values.pop("channels", [])
        hashtags = values.pop("hashtags", [])
        campaign = AIMarketingCampaign(
            **values,
            channels_json=json.dumps(channels, ensure_ascii=False),
            hashtags_json=json.dumps(hashtags, ensure_ascii=False),
        )
        self.session.add(campaign)
        await self.session.flush()
        await self.session.refresh(campaign)
        return campaign

    async def get(self, campaign_id: int) -> AIMarketingCampaign | None:
        return await self.session.get(AIMarketingCampaign, campaign_id)

    async def list(
        self,
        *,
        page: int,
        page_size: int,
        campaign_type: str | None = None,
        campaign_status: str | None = None,
    ) -> tuple[list[AIMarketingCampaign], int]:
        conditions = []
        if campaign_type:
            conditions.append(
                AIMarketingCampaign.campaign_type == campaign_type
            )
        if campaign_status:
            conditions.append(AIMarketingCampaign.status == campaign_status)
        total = int(
            (
                await self.session.execute(
                    select(func.count(AIMarketingCampaign.id)).where(
                        *conditions
                    )
                )
            ).scalar_one()
        )
        result = await self.session.execute(
            select(AIMarketingCampaign)
            .where(*conditions)
            .order_by(
                AIMarketingCampaign.updated_at.desc(),
                AIMarketingCampaign.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def update(
        self,
        campaign: AIMarketingCampaign,
        data: dict[str, Any],
    ) -> AIMarketingCampaign:
        values = dict(data)
        if "channels" in values:
            campaign.channels_json = json.dumps(
                values.pop("channels") or [],
                ensure_ascii=False,
            )
        if "hashtags" in values:
            campaign.hashtags_json = json.dumps(
                values.pop("hashtags") or [],
                ensure_ascii=False,
            )
        for field, value in values.items():
            setattr(campaign, field, value)
        campaign.status = "draft"
        campaign.approved_by = None
        campaign.approved_at = None
        campaign.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(campaign)
        return campaign

    async def approve(
        self,
        campaign: AIMarketingCampaign,
        *,
        approved_by: int,
    ) -> AIMarketingCampaign:
        now = datetime.now(UTC)
        campaign.status = "approved"
        campaign.approved_by = approved_by
        campaign.approved_at = now
        campaign.updated_at = now
        await self.session.flush()
        await self.session.refresh(campaign)
        return campaign

    async def archive(
        self,
        campaign: AIMarketingCampaign,
    ) -> AIMarketingCampaign:
        campaign.status = "archived"
        campaign.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(campaign)
        return campaign
