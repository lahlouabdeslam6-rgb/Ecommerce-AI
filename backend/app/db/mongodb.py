from typing import Any

from pymongo import AsyncMongoClient

from app.core.config import settings


mongo_client: AsyncMongoClient | None = None
mongo_database: Any | None = None


async def connect_mongodb() -> None:
    global mongo_client, mongo_database

    mongo_client = AsyncMongoClient(
        settings.mongodb_url,
        serverSelectionTimeoutMS=5000,
    )
    await mongo_client.admin.command("ping")
    mongo_database = mongo_client[settings.mongodb_database]


async def disconnect_mongodb() -> None:
    global mongo_client, mongo_database

    if mongo_client is not None:
        await mongo_client.close()
    mongo_client = None
    mongo_database = None


async def check_mongodb() -> bool:
    if mongo_client is None:
        return False

    result = await mongo_client.admin.command("ping")
    return result.get("ok") == 1.0
