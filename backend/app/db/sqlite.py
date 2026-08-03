from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


Path("data").mkdir(parents=True, exist_ok=True)

sqlite_engine = create_async_engine(settings.sqlite_url, pool_pre_ping=True)


@event.listens_for(sqlite_engine.sync_engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
SqliteSession = async_sessionmaker(
    bind=sqlite_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_sqlite_session() -> AsyncIterator[AsyncSession]:
    async with SqliteSession() as session:
        yield session


async def initialize_sqlite() -> None:
    from app import models  # noqa: F401

    async with sqlite_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        columns = {
            row[1]
            for row in (
                await connection.exec_driver_sql("PRAGMA table_info(orders)")
            ).fetchall()
        }
        for name, definition in {
            "card_last4": "VARCHAR(4)",
            "card_brand": "VARCHAR(30)",
            "payment_reference": "VARCHAR(120)",
        }.items():
            if name not in columns:
                await connection.exec_driver_sql(
                    f"ALTER TABLE orders ADD COLUMN {name} {definition}"
                )
        order_item_columns = {
            row[1]
            for row in (
                await connection.exec_driver_sql("PRAGMA table_info(order_items)")
            ).fetchall()
        }
        for name, definition in {
            "pack_id": "INTEGER REFERENCES packs(id) ON DELETE SET NULL",
            "item_type": "VARCHAR(20) NOT NULL DEFAULT 'product'",
        }.items():
            if name not in order_item_columns:
                await connection.exec_driver_sql(
                    f"ALTER TABLE order_items ADD COLUMN {name} {definition}"
                )
        user_columns = {
            row[1]
            for row in (
                await connection.exec_driver_sql("PRAGMA table_info(users)")
            ).fetchall()
        }
        for name, definition in {
            "is_email_verified": "BOOLEAN NOT NULL DEFAULT 0",
            "is_deleted": "BOOLEAN NOT NULL DEFAULT 0",
            "token_version": "INTEGER NOT NULL DEFAULT 0",
            "verification_token_hash": "VARCHAR(64)",
            "password_reset_token_hash": "VARCHAR(64)",
            "password_reset_expires_at": "DATETIME",
            "failed_login_attempts": "INTEGER NOT NULL DEFAULT 0",
            "locked_until": "DATETIME",
        }.items():
            if name not in user_columns:
                await connection.exec_driver_sql(
                    f"ALTER TABLE users ADD COLUMN {name} {definition}"
                )


async def disconnect_sqlite() -> None:
    await sqlite_engine.dispose()


async def check_sqlite() -> bool:
    async with sqlite_engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))
        return result.scalar_one() == 1
