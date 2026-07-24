import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_safety import AISafetyReview


class SafetyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: dict[str, Any]) -> AISafetyReview:
        values = dict(data)
        reasons = values.pop("reasons", [])
        recommendations = values.pop("recommendations", [])
        matched_rules = values.pop("matched_rules", [])
        review = AISafetyReview(
            **values,
            reasons_json=json.dumps(reasons, ensure_ascii=False),
            recommendations_json=json.dumps(
                recommendations,
                ensure_ascii=False,
            ),
            matched_rules_json=json.dumps(
                matched_rules,
                ensure_ascii=False,
            ),
        )
        self.session.add(review)
        await self.session.flush()
        await self.session.refresh(review)
        return review

    async def list(
        self,
        *,
        page: int,
        page_size: int,
        review_status: str | None = None,
        source_type: str | None = None,
    ) -> tuple[list[AISafetyReview], int]:
        conditions = []
        if review_status:
            conditions.append(AISafetyReview.status == review_status)
        if source_type:
            conditions.append(AISafetyReview.source_type == source_type)
        total = int(
            (
                await self.session.execute(
                    select(func.count(AISafetyReview.id)).where(*conditions)
                )
            ).scalar_one()
        )
        result = await self.session.execute(
            select(AISafetyReview)
            .where(*conditions)
            .order_by(
                AISafetyReview.created_at.desc(),
                AISafetyReview.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total
