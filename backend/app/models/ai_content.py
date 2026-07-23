import json
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.sqlite import Base


class AIContent(Base):
    __tablename__ = "ai_contents"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_type: Mapped[str] = mapped_column(String(40), index=True)
    topic: Mapped[str] = mapped_column(String(300))
    objective: Mapped[str | None] = mapped_column(String(500), nullable=True)
    audience: Mapped[str] = mapped_column(String(120), default="sportifs au Maroc")
    tone: Mapped[str] = mapped_column(String(30), default="premium")
    language: Mapped[str] = mapped_column(String(10), default="fr")
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(180))
    subtitle: Mapped[str | None] = mapped_column(String(300), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    cta_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    hashtags_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    model: Mapped[str] = mapped_column(String(120))
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
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
    def hashtags(self) -> list[str]:
        try:
            value = json.loads(self.hashtags_json)
            return value if isinstance(value, list) else []
        except json.JSONDecodeError:
            return []
