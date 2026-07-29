import json
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.sqlite import Base


class AIMarketingCampaign(Base):
    __tablename__ = "ai_marketing_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_type: Mapped[str] = mapped_column(String(40), index=True)
    topic: Mapped[str] = mapped_column(String(300))
    objective: Mapped[str] = mapped_column(String(500))
    audience: Mapped[str] = mapped_column(String(160))
    tone: Mapped[str] = mapped_column(String(30), default="premium")
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    promotion_kind: Mapped[str | None] = mapped_column(
        String(30), nullable=True, index=True
    )
    selection_mode: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )
    product_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    selection_scores_json: Mapped[str] = mapped_column(Text, default="[]")
    discount_percentage: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    offer_details: Mapped[str | None] = mapped_column(String(500), nullable=True)
    channels_json: Mapped[str] = mapped_column(Text, default="[]")
    campaign_title: Mapped[str] = mapped_column(String(180))
    headline: Mapped[str] = mapped_column(String(220))
    core_message: Mapped[str] = mapped_column(Text)
    email_subject: Mapped[str | None] = mapped_column(String(180), nullable=True)
    email_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    whatsapp_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    social_caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    cta_label: Mapped[str] = mapped_column(String(80))
    hashtags_json: Mapped[str] = mapped_column(Text, default="[]")
    recommended_schedule: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    model: Mapped[str] = mapped_column(String(120))
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    @property
    def channels(self) -> list[str]:
        return self._json_list(self.channels_json)

    @property
    def hashtags(self) -> list[str]:
        return self._json_list(self.hashtags_json)

    @property
    def product_ids(self) -> list[int]:
        return [
            int(value)
            for value in self._json_list(self.product_ids_json)
            if isinstance(value, int) or str(value).isdigit()
        ]

    @property
    def selection_scores(self) -> list[dict]:
        try:
            result = json.loads(self.selection_scores_json)
            return result if isinstance(result, list) else []
        except json.JSONDecodeError:
            return []

    @staticmethod
    def _json_list(value: str) -> list[str]:
        try:
            result = json.loads(value)
            return result if isinstance(result, list) else []
        except json.JSONDecodeError:
            return []
