from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.sqlite import Base


class Pack(Base):
    __tablename__ = "packs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    highlights_json: Mapped[str] = mapped_column(Text, default="[]")
    main_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    gallery_json: Mapped[str] = mapped_column(Text, default="[]")
    regular_price: Mapped[float] = mapped_column(Float)
    discount_percentage: Mapped[float] = mapped_column(Float, default=0)
    promotional_price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="MAD")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    source: Mapped[str] = mapped_column(String(20), default="admin")
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_marketing_campaigns.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    items: Mapped[list["PackItem"]] = relationship(
        back_populates="pack", cascade="all, delete-orphan", lazy="selectin"
    )


class PackItem(Base):
    __tablename__ = "pack_items"
    __table_args__ = (UniqueConstraint("pack_id", "product_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pack_id: Mapped[int] = mapped_column(
        ForeignKey("packs.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(Integer, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    position: Mapped[int] = mapped_column(Integer, default=0)

    pack: Mapped[Pack] = relationship(back_populates="items")

