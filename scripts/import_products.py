import csv
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pymongo import MongoClient, UpdateOne


def optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def optional_float(value: str | None) -> float | None:
    cleaned = optional_text(value)
    return float(cleaned) if cleaned is not None else None


def optional_int(value: str | None) -> int | None:
    cleaned = optional_text(value)
    return int(float(cleaned)) if cleaned is not None else None


def compact(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def ingredient_from_row(row: dict[str, str]) -> dict[str, Any]:
    return compact(
        {
            "name": optional_text(row.get("ingredient")),
            "form": optional_text(row.get("ingredient_form")),
            "category": optional_text(row.get("ingredient_category")),
            "amount_per_serving_mg": optional_float(
                row.get("amount_per_serving_mg")
            ),
            "is_proprietary_blend": row.get("is_proprietary_blend", "").strip()
            == "1",
            "recommended_daily_mg": optional_float(
                row.get("recommended_daily_mg")
            ),
            "upper_safety_limit_mg": optional_float(
                row.get("upper_safety_limit_mg")
            ),
            "pubchem_cid": optional_int(row.get("pubchem_cid")),
            "molecular_formula": optional_text(row.get("molecular_formula")),
            "molecular_weight": optional_float(row.get("molecular_weight")),
            "inchikey": optional_text(row.get("inchikey")),
            "canonical_smiles": optional_text(row.get("canonical_smiles")),
        }
    )


def load_products(csv_path: Path) -> dict[int, dict[str, Any]]:
    products: dict[int, dict[str, Any]] = {}
    ingredient_keys: dict[int, set[tuple[tuple[str, Any], ...]]] = {}

    with csv_path.open(encoding="utf-8-sig", newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            product_id = optional_int(row.get("product_id"))
            if product_id is None:
                continue

            if product_id not in products:
                products[product_id] = compact(
                    {
                        "product_id": product_id,
                        "brand": optional_text(row.get("brand")),
                        "name": optional_text(row.get("product_name")),
                        "upc_barcode": optional_text(row.get("upc_barcode")),
                        "form_type": optional_text(row.get("form_type")),
                        "serving_size": compact(
                            {
                                "count": optional_float(
                                    row.get("serving_size_count")
                                ),
                                "unit": optional_text(row.get("serving_size_unit")),
                            }
                        ),
                        "servings_per_container": optional_float(
                            row.get("servings_per_container")
                        ),
                        "source": compact(
                            {
                                "dsld_label_id": optional_int(
                                    row.get("dsld_label_id")
                                ),
                                "url": optional_text(row.get("source_url")),
                                "dataset_version": optional_text(
                                    row.get("dataset_version")
                                ),
                            }
                        ),
                        "ingredients": [],
                    }
                )
                ingredient_keys[product_id] = set()

            ingredient = ingredient_from_row(row)
            ingredient_key = tuple(sorted(ingredient.items()))
            if ingredient and ingredient_key not in ingredient_keys[product_id]:
                products[product_id]["ingredients"].append(ingredient)
                ingredient_keys[product_id].add(ingredient_key)

    return products


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python import_products.py <csv-path>")

    csv_path = Path(sys.argv[1])
    if not csv_path.is_file():
        raise SystemExit(f"CSV file not found: {csv_path}")

    mongodb_url = os.environ["MONGODB_URL"]
    database_name = os.getenv("MONGODB_DATABASE", "ecommerce_ai")
    products = load_products(csv_path)
    now = datetime.now(UTC)

    client = MongoClient(mongodb_url, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        collection = client[database_name]["products"]
        collection.create_index("product_id", unique=True)

        operations = []
        for product in products.values():
            product["updated_at"] = now
            operations.append(
                UpdateOne(
                    {"product_id": product["product_id"]},
                    {
                        "$set": product,
                        "$setOnInsert": {"created_at": now},
                    },
                    upsert=True,
                )
            )

        result = collection.bulk_write(operations, ordered=False)
        print(
            {
                "source_rows": sum(
                    len(product["ingredients"]) for product in products.values()
                ),
                "products_processed": len(products),
                "inserted": result.upserted_count,
                "updated": result.modified_count,
                "collection_count": collection.count_documents({}),
            }
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
