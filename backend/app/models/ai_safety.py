import json
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.sqlite import Base


class AISafetyReview(Base):
    __tablename__ = "ai_safety_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(50), index=True)
    source_id: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    risk_level: Mapped[str] = mapped_column(String(20), index=True)
    reasons_json: Mapped[str] = mapped_column(Text, default="[]")
    recommendations_json: Mapped[str] = mapped_column(Text, default="[]")
    matched_rules_json: Mapped[str] = mapped_column(Text, default="[]")
    excerpt: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(120))
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )

    @property
    def reasons(self) -> list[str]:
        return self._json_list(self.reasons_json)

    @property
    def recommendations(self) -> list[str]:
        return self._json_list(self.recommendations_json)

    @property
    def matched_rules(self) -> list[str]:
        return self._json_list(self.matched_rules_json)

    @staticmethod
    def _json_list(value: str) -> list[str]:
        try:
            result = json.loads(value)
            return result if isinstance(result, list) else []
        except json.JSONDecodeError:
            return []
