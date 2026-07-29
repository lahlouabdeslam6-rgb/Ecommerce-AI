from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.sqlite import Base


class ProductCost(Base):
    __tablename__ = "product_costs"

    product_id: Mapped[int] = mapped_column(primary_key=True)
    cost_price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="MAD")
    updated_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class ProductView(Base):
    __tablename__ = "product_views"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(Integer, index=True)
    viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )
