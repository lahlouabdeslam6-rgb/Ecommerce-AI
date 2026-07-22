import glob
import sqlite3

from pymongo import MongoClient

from app.core.config import settings


sqlite = sqlite3.connect("/app/data/ecommerce.db")
mongo = MongoClient(settings.mongodb_url)[settings.mongodb_database]

print(
    {
        "integrity": sqlite.execute("PRAGMA integrity_check").fetchone()[0],
        "qa_users": sqlite.execute(
            "SELECT count(1) FROM users WHERE email LIKE ?",
            ("qa-%@example.com",),
        ).fetchone()[0],
        "qa_products": mongo.products.count_documents({"brand": "NUTRIFIT QA"}),
        "qa_images": len(
            glob.glob("/app/app/static/uploads/products/23447-*")
        ),
    }
)
