import os
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from pymongo import MongoClient, UpdateOne


def commercial_category(product: dict[str, Any]) -> str:
    categories = [
        ingredient.get("category")
        for ingredient in product.get("ingredients", [])
        if ingredient.get("category")
    ]
    if not categories:
        return "other"
    return Counter(categories).most_common(1)[0][0].replace("_", " ")


def demo_price(product_id: int) -> float:
    return round(79 + ((product_id * 37) % 421) + 0.90, 2)


def demo_stock(product_id: int) -> int:
    return 10 + ((product_id * 17) % 91)


def main() -> None:
    client = MongoClient(os.environ["MONGODB_URL"], serverSelectionTimeoutMS=5000)
    database_name = os.getenv("MONGODB_DATABASE", "ecommerce_ai")
    try:
        collection = client[database_name]["products"]
        operations: list[UpdateOne] = []

        for product in collection.find({}):
            product_id = int(product["product_id"])
            name = product.get("name") or "Dietary supplement"
            brand = product.get("brand") or "Unknown brand"
            updates: dict[str, Any] = {}

            if product.get("description") is None:
                updates["description"] = (
                    f"{name} by {brand}. Product information is based on the "
                    "manufacturer label; follow the label directions and warnings."
                )
            if product.get("category") is None:
                updates["category"] = commercial_category(product)
            if product.get("price") is None:
                updates["price"] = demo_price(product_id)
            if product.get("currency") is None:
                updates["currency"] = "MAD"
            if product.get("stock") is None:
                updates["stock"] = demo_stock(product_id)
            if product.get("is_active") is None:
                updates["is_active"] = True
            if updates:
                updates["updated_at"] = datetime.now(UTC)
                operations.append(
                    UpdateOne({"_id": product["_id"]}, {"$set": updates})
                )

        result = collection.bulk_write(operations, ordered=False) if operations else None
        print(
            {
                "products": collection.count_documents({}),
                "updated": result.modified_count if result else 0,
                "price_note": "Generated demo prices in MAD; admin can edit them.",
            }
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
