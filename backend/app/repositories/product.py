import re
from datetime import UTC, datetime
from typing import Any

from pymongo import ReturnDocument

from app.db import mongodb


KNOWN_FLAVORS = (
    "Birthday Cake",
    "Mixed Berry",
    "Strawberry",
    "Blueberry",
    "Tangerine",
    "Pineapple",
    "Chocolate",
    "Spearmint",
    "Cherry",
    "Orange",
    "Grape",
    "Peach",
    "Berry",
    "Fruit",
)


class ProductRepository:
    @property
    def collection(self) -> Any:
        if mongodb.mongo_database is None:
            raise RuntimeError("MongoDB is not connected")
        return mongodb.mongo_database["products"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("product_id", unique=True)
        await self.collection.create_index("name")
        await self.collection.create_index("brand")
        await self.collection.create_index("category")
        await self.collection.create_index("is_active")
        await self.collection.create_index("ingredients.name")
        await self.collection.create_index("slug")

        latest_product = await self.collection.find_one(
            {},
            {"product_id": 1},
            sort=[("product_id", -1)],
        )
        highest_product_id = latest_product["product_id"] if latest_product else 0
        await mongodb.mongo_database["counters"].update_one(
            {"_id": "products"},
            {"$max": {"sequence": highest_product_id}},
            upsert=True,
        )

    async def next_product_id(self) -> int:
        counter = await mongodb.mongo_database["counters"].find_one_and_update(
            {"_id": "products"},
            {"$inc": {"sequence": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int(counter["sequence"])

    async def list_products(
        self,
        *,
        skip: int,
        limit: int,
        search: str | None = None,
        brand: str | None = None,
        ingredient: str | None = None,
        category: str | None = None,
        flavor: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        in_stock: bool | None = None,
        sort_by: str = "newest",
        active_only: bool = True,
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {}

        if active_only:
            query["is_active"] = True

        if search:
            escaped_search = re.escape(search.strip())
            query["$or"] = [
                {"name": {"$regex": escaped_search, "$options": "i"}},
                {"brand": {"$regex": escaped_search, "$options": "i"}},
            ]
        if brand:
            query["brand"] = {
                "$regex": f"^{re.escape(brand.strip())}$",
                "$options": "i",
            }
        if ingredient:
            query["ingredients.name"] = {
                "$regex": re.escape(ingredient.strip()),
                "$options": "i",
            }
        if category:
            query["category"] = {
                "$regex": f"^{re.escape(category.strip())}$",
                "$options": "i",
            }
        if flavor:
            query["name"] = {
                "$regex": rf"\b{re.escape(flavor.strip())}\b",
                "$options": "i",
            }
        if min_price is not None or max_price is not None:
            price_query: dict[str, float] = {}
            if min_price is not None:
                price_query["$gte"] = min_price
            if max_price is not None:
                price_query["$lte"] = max_price
            query["price"] = price_query
        if in_stock is True:
            query["stock"] = {"$gt": 0}
        elif in_stock is False:
            query["stock"] = 0

        total = await self.collection.count_documents(query)
        sort_options = {
            "newest": [("created_at", -1), ("product_id", -1)],
            "name": [("name", 1), ("product_id", 1)],
            "price_asc": [("price", 1), ("product_id", 1)],
            "price_desc": [("price", -1), ("product_id", 1)],
            "stock_desc": [("stock", -1), ("product_id", 1)],
        }
        cursor = (
            self.collection.find(query, {"_id": 0})
            .sort(sort_options[sort_by])
            .skip(skip)
            .limit(limit)
        )
        products = await cursor.to_list(length=limit)
        return products, total

    async def get_by_product_id(self, product_id: int) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {"product_id": product_id},
            {"_id": 0},
        )

    async def create_product(self, data: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        product = {
            **data,
            "product_id": await self.next_product_id(),
            "created_at": now,
            "updated_at": now,
        }
        await self.collection.insert_one(product)
        product.pop("_id", None)
        return product

    async def update_product(
        self,
        product_id: int,
        data: dict[str, Any],
    ) -> dict[str, Any] | None:
        return await self.collection.find_one_and_update(
            {"product_id": product_id},
            {"$set": {**data, "updated_at": datetime.now(UTC)}},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )

    async def update_stock(
        self,
        product_id: int,
        stock: int,
    ) -> dict[str, Any] | None:
        return await self.update_product(product_id, {"stock": stock})

    async def add_image(
        self,
        product_id: int,
        image_url: str,
    ) -> dict[str, Any] | None:
        return await self.collection.find_one_and_update(
            {"product_id": product_id},
            {
                "$addToSet": {"images": image_url},
                "$set": {"updated_at": datetime.now(UTC)},
            },
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )

    async def set_images(
        self,
        product_id: int,
        images: list[str],
    ) -> dict[str, Any] | None:
        return await self.update_product(product_id, {"images": images})

    async def delete_product(self, product_id: int) -> bool:
        result = await self.collection.delete_one({"product_id": product_id})
        return result.deleted_count == 1

    async def get_many_by_ids(
        self,
        product_ids: list[int],
    ) -> dict[int, dict[str, Any]]:
        if not product_ids:
            return {}
        cursor = self.collection.find(
            {"product_id": {"$in": product_ids}},
            {"_id": 0},
        )
        products = await cursor.to_list(length=len(product_ids))
        return {int(product["product_id"]): product for product in products}

    async def recommendation_candidates(
        self,
        *,
        exclude_ids: list[int],
        max_price: float | None,
        limit: int = 120,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {
            "is_active": True,
            "stock": {"$gt": 0},
            "price": {"$ne": None},
        }
        if exclude_ids:
            query["product_id"] = {"$nin": exclude_ids}
        if max_price is not None:
            query["price"] = {"$ne": None, "$lte": max_price}
        cursor = (
            self.collection.find(query, {"_id": 0})
            .sort([("stock", -1), ("product_id", 1)])
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def reserve_stock(self, product_id: int, quantity: int) -> bool:
        product = await self.collection.find_one_and_update(
            {
                "product_id": product_id,
                "is_active": True,
                "stock": {"$gte": quantity},
            },
            {
                "$inc": {"stock": -quantity},
                "$set": {"updated_at": datetime.now(UTC)},
            },
            return_document=ReturnDocument.AFTER,
        )
        return product is not None

    async def restore_stock(self, product_id: int, quantity: int) -> None:
        await self.collection.update_one(
            {"product_id": product_id},
            {
                "$inc": {"stock": quantity},
                "$set": {"updated_at": datetime.now(UTC)},
            },
        )

    async def catalog_filters(self) -> dict[str, list[str]]:
        brands = await self.collection.distinct("brand", {"is_active": True})
        categories = await self.collection.distinct(
            "category", {"is_active": True}
        )
        product_names = await self.collection.distinct(
            "name", {"is_active": True}
        )
        flavors: set[str] = set()
        for name in product_names:
            if not name:
                continue
            for flavor in KNOWN_FLAVORS:
                if re.search(rf"\b{re.escape(flavor)}\b", name, re.IGNORECASE):
                    flavors.add(flavor)
                    break
        return {
            "brands": sorted(value for value in brands if value),
            "categories": sorted(value for value in categories if value),
            "flavors": sorted(flavors),
        }

    async def catalog_counts(self) -> dict[str, int]:
        return {
            "products": await self.collection.count_documents({}),
            "active_products": await self.collection.count_documents(
                {"is_active": True}
            ),
            "low_stock_products": await self.collection.count_documents(
                {"is_active": True, "stock": {"$lte": 5}}
            ),
        }
