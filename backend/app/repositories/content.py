import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_content import AIContent


class ContentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: dict[str, Any]) -> AIContent:
        hashtags = data.pop("hashtags", [])
        item = AIContent(
            **data,
            hashtags_json=json.dumps(hashtags, ensure_ascii=False),
        )
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def get(self, content_id: int) -> AIContent | None:
        return await self.session.get(AIContent, content_id)

    async def list(
        self,
        *,
        page: int,
        page_size: int,
        content_type: str | None = None,
        content_status: str | None = None,
    ) -> tuple[list[AIContent], int]:
        conditions = []
        if content_type:
            conditions.append(AIContent.content_type == content_type)
        if content_status:
            conditions.append(AIContent.status == content_status)
        total = int(
            (
                await self.session.execute(
                    select(func.count(AIContent.id)).where(*conditions)
                )
            ).scalar_one()
        )
        result = await self.session.execute(
            select(AIContent)
            .where(*conditions)
            .order_by(AIContent.updated_at.desc(), AIContent.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def update(
        self,
        item: AIContent,
        data: dict[str, Any],
    ) -> AIContent:
        if "hashtags" in data:
            item.hashtags_json = json.dumps(
                data.pop("hashtags") or [],
                ensure_ascii=False,
            )
        for field, value in data.items():
            setattr(item, field, value)
        item.status = "draft"
        item.published_at = None
        item.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def publish(self, item: AIContent) -> AIContent:
        if item.content_type in {"homepage_hero", "promotion"}:
            await self.session.execute(
                update(AIContent)
                .where(
                    AIContent.content_type == item.content_type,
                    AIContent.status == "published",
                    AIContent.id != item.id,
                )
                .values(status="archived", published_at=None)
            )
        now = datetime.now(UTC)
        item.status = "published"
        item.published_at = now
        item.updated_at = now
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def archive(self, item: AIContent) -> AIContent:
        item.status = "archived"
        item.published_at = None
        item.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def latest_published(
        self,
        content_type: str,
    ) -> AIContent | None:
        result = await self.session.execute(
            select(AIContent)
            .where(
                AIContent.content_type == content_type,
                AIContent.status == "published",
            )
            .order_by(AIContent.published_at.desc(), AIContent.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
