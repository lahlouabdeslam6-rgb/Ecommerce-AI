import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.pack import Pack, PackItem


class PackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _query():
        return select(Pack).options(selectinload(Pack.items))

    async def get(self, pack_id: int) -> Pack | None:
        result = await self.session.execute(self._query().where(Pack.id == pack_id))
        return result.scalar_one_or_none()

    async def get_by_campaign(self, campaign_id: int) -> Pack | None:
        result = await self.session.execute(
            self._query().where(Pack.campaign_id == campaign_id)
        )
        return result.scalar_one_or_none()

    async def list_public(self, now: datetime) -> list[Pack]:
        result = await self.session.execute(
            self._query()
            .where(
                Pack.is_active.is_(True),
                or_(Pack.starts_at.is_(None), Pack.starts_at <= now),
                or_(Pack.ends_at.is_(None), Pack.ends_at >= now),
            )
            .order_by(Pack.updated_at.desc(), Pack.id.desc())
        )
        return list(result.scalars().all())

    async def list_admin(self, search: str | None = None) -> list[Pack]:
        query = self._query()
        if search:
            query = query.where(Pack.name.ilike(f"%{search.strip()}%"))
        result = await self.session.execute(
            query.order_by(Pack.updated_at.desc(), Pack.id.desc())
        )
        return list(result.scalars().all())

    async def expire_due(self, now: datetime) -> int:
        result = await self.session.execute(
            update(Pack)
            .where(
                Pack.is_active.is_(True),
                Pack.ends_at.is_not(None),
                Pack.ends_at < now,
            )
            .values(is_active=False, updated_at=now)
        )
        return int(result.rowcount or 0)

    async def slug_exists(self, slug: str, *, exclude_id: int | None = None) -> bool:
        query = select(func.count(Pack.id)).where(Pack.slug == slug)
        if exclude_id is not None:
            query = query.where(Pack.id != exclude_id)
        return bool((await self.session.execute(query)).scalar_one())

    async def create(self, data: dict[str, Any], items: list[dict[str, int]]) -> Pack:
        values = dict(data)
        highlights = values.pop("highlights", [])
        gallery = values.pop("gallery", [])
        pack = Pack(
            **values,
            highlights_json=json.dumps(highlights, ensure_ascii=False),
            gallery_json=json.dumps(gallery, ensure_ascii=False),
            items=[PackItem(**item, position=index) for index, item in enumerate(items)],
        )
        self.session.add(pack)
        await self.session.flush()
        return await self.get(pack.id)  # type: ignore[return-value]

    async def update(
        self,
        pack: Pack,
        values: dict[str, Any],
        items: list[dict[str, int]] | None = None,
    ) -> Pack:
        if "highlights" in values:
            pack.highlights_json = json.dumps(values.pop("highlights"), ensure_ascii=False)
        if "gallery" in values:
            pack.gallery_json = json.dumps(values.pop("gallery"), ensure_ascii=False)
        for key, value in values.items():
            setattr(pack, key, value)
        if items is not None:
            await self.session.execute(delete(PackItem).where(PackItem.pack_id == pack.id))
            pack.items = [
                PackItem(pack_id=pack.id, **item, position=index)
                for index, item in enumerate(items)
            ]
        pack.updated_at = datetime.now(UTC)
        await self.session.flush()
        return await self.get(pack.id)  # type: ignore[return-value]

    async def delete(self, pack: Pack) -> None:
        await self.session.delete(pack)
        await self.session.flush()
