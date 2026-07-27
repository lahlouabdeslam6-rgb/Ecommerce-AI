"""Destructive-on-temp-data end-to-end QA for a running local Docker stack."""

import os
import sqlite3
import time
from pathlib import Path

import httpx


BASE_URL = os.getenv("QA_BASE_URL", "http://localhost:8000")
ADMIN_EMAIL = os.environ["QA_ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["QA_ADMIN_PASSWORD"]
STAMP = str(int(time.time()))
CUSTOMER_EMAIL = f"qa-customer-{STAMP}@example.com"
SUPPORT_EMAIL = f"qa-support-{STAMP}@example.com"
INITIAL_PASSWORD = "QaSecure!2026"
RESET_PASSWORD = "QaSecure!2027"

client = httpx.Client(base_url=BASE_URL, timeout=20)
created: dict[str, int] = {}
checks: list[str] = []


def expect(response: httpx.Response, status_code: int, label: str):
    if response.status_code != status_code:
        raise AssertionError(
            f"{label}: expected {status_code}, got {response.status_code}: "
            f"{response.text[:500]}"
        )
    checks.append(label)
    if status_code == 204:
        return None
    return response.json()


def login(email: str, password: str) -> dict:
    return expect(
        client.post(
            "/api/auth/login",
            data={"username": email, "password": password},
        ),
        200,
        f"login:{email}",
    )


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def cleanup() -> None:
    product_id = created.get("product")
    admin_token = created.get("admin_token")
    if product_id and admin_token:
        client.delete(
            f"/api/products/{product_id}",
            headers=bearer(str(admin_token)),
        )
        upload_directory = Path("/app/app/static/uploads/products")
        for image_path in upload_directory.glob(f"{product_id}-*"):
            if image_path.is_file() and image_path.parent == upload_directory:
                image_path.unlink()

    database_path = Path("/app/data/ecommerce.db")
    if not database_path.exists():
        return
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys=ON")
    customer_id = created.get("customer")
    support_id = created.get("support")
    order_id = created.get("order")
    guest_order_id = created.get("guest_order")
    ticket_id = created.get("ticket")
    user_ids = [value for value in (customer_id, support_id) if value]

    if ticket_id:
        connection.execute(
            "DELETE FROM support_messages WHERE ticket_id = ?", (ticket_id,)
        )
        connection.execute("DELETE FROM support_tickets WHERE id = ?", (ticket_id,))
    for value in (order_id, guest_order_id):
        if value:
            connection.execute("DELETE FROM order_items WHERE order_id = ?", (value,))
            connection.execute("DELETE FROM orders WHERE id = ?", (value,))
    for user_id in user_ids:
        connection.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM audit_logs WHERE actor_id = ?", (user_id,))
    if product_id:
        connection.execute(
            "DELETE FROM stock_movements WHERE product_id = ?", (product_id,)
        )
        connection.execute(
            "DELETE FROM audit_logs WHERE entity_type = 'product' AND entity_id = ?",
            (str(product_id),),
        )
    for entity_type, entity_id in (
        ("order", order_id),
        ("order", guest_order_id),
        ("ticket", ticket_id),
        ("user", customer_id),
        ("user", support_id),
    ):
        if entity_id:
            connection.execute(
                "DELETE FROM audit_logs WHERE entity_type = ? AND entity_id = ?",
                (entity_type, str(entity_id)),
            )
    for value in (order_id, guest_order_id):
        if value:
            connection.execute(
                "DELETE FROM notifications WHERE link LIKE ? OR message LIKE ?",
                (f"%order={value}%", f"%#{value}%"),
            )
    if ticket_id:
        connection.execute(
            "DELETE FROM notifications WHERE link LIKE ? OR message LIKE ?",
            (f"%ticket={ticket_id}%", f"%#{ticket_id}%"),
        )
    for user_id in user_ids:
        connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
    connection.commit()
    connection.close()


try:
    health = expect(client.get("/health"), 200, "health")
    assert health["status"] == "healthy"

    catalogue = expect(
        client.get(
            "/api/products",
            params={"page_size": 3, "sort_by": "price_asc", "in_stock": True},
        ),
        200,
        "catalogue filters and sorting",
    )
    assert catalogue["total"] > 0 and len(catalogue["items"]) <= 3
    expect(client.get("/api/products/filters"), 200, "catalogue filter values")
    expect(
        client.get("/api/products/999999999"),
        404,
        "missing product handling",
    )
    expect(
        client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}),
        401,
        "guest cart protection",
    )

    admin_tokens = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    created["admin_token"] = admin_tokens["access_token"]
    refreshed_admin = expect(
        client.post(
            "/api/auth/refresh",
            json={"refresh_token": admin_tokens["refresh_token"]},
        ),
        200,
        "admin refresh token",
    )
    admin_headers = bearer(refreshed_admin["access_token"])
    me = expect(client.get("/api/auth/me", headers=admin_headers), 200, "admin me")
    assert me["role"] == "admin"
    expect(
        client.get("/api/auth/permissions", headers=admin_headers),
        200,
        "admin permissions",
    )
    for path, label in (
        ("/api/admin/dashboard", "admin dashboard"),
        ("/api/admin/users?page_size=100", "admin users"),
        ("/api/admin/support-users?page_size=100", "admin support accounts"),
        ("/api/admin/orders?page_size=10", "admin orders"),
        ("/api/admin/audit-logs?page_size=10", "admin audit"),
        ("/api/stock-movements?page_size=10", "stock history"),
        ("/api/admin/metrics", "monitoring metrics"),
    ):
        expect(client.get(path, headers=admin_headers), 200, label)

    support = expect(
        client.post(
            "/api/admin/support-users",
            headers=admin_headers,
            json={
                "email": SUPPORT_EMAIL,
                "password": INITIAL_PASSWORD,
                "full_name": "QA Support",
                "is_active": True,
            },
        ),
        201,
        "create support account",
    )
    created["support"] = support["id"]
    support_tokens = login(SUPPORT_EMAIL, INITIAL_PASSWORD)
    support_headers = bearer(support_tokens["access_token"])
    expect(
        client.get("/api/support/dashboard", headers=support_headers),
        200,
        "support dashboard",
    )
    expect(
        client.post(
            "/api/products",
            headers=support_headers,
            json={
                "brand": "Forbidden",
                "name": "Forbidden",
                "price": 1,
                "stock": 1,
            },
        ),
        403,
        "support cannot create products",
    )

    product = expect(
        client.post(
            "/api/products",
            headers=admin_headers,
            json={
                "brand": "NUTRIFIT QA",
                "name": f"QA Whey {STAMP}",
                "description": "Temporary end-to-end QA product",
                "category": "protein",
                "price": 199.9,
                "currency": "MAD",
                "stock": 12,
                "is_active": True,
                "images": [],
                "ingredients": [],
            },
        ),
        201,
        "admin creates product",
    )
    product_id = product["product_id"]
    created["product"] = product_id

    product = expect(
        client.patch(
            f"/api/products/{product_id}",
            headers=support_headers,
            json={"price": 209.9, "stock": 15},
        ),
        200,
        "support updates product and stock",
    )
    assert product["price"] == 209.9 and product["stock"] == 15

    png_a = b"\x89PNG\r\n\x1a\nqa-image-a"
    png_b = b"\x89PNG\r\n\x1a\nqa-image-b"
    product = expect(
        client.post(
            f"/api/products/{product_id}/images",
            headers=support_headers,
            files={"image": ("qa-a.png", png_a, "image/png")},
        ),
        200,
        "upload first product image",
    )
    product = expect(
        client.post(
            f"/api/products/{product_id}/images",
            headers=support_headers,
            files={"image": ("qa-b.png", png_b, "image/png")},
        ),
        200,
        "upload second product image",
    )
    assert len(product["images"]) == 2
    reordered = list(reversed(product["images"]))
    product = expect(
        client.patch(
            f"/api/products/{product_id}/images/order",
            headers=support_headers,
            json={"images": reordered},
        ),
        200,
        "reorder product images",
    )
    product = expect(
        client.delete(
            f"/api/products/{product_id}/images",
            headers=support_headers,
            params={"image_url": product["images"][1]},
        ),
        200,
        "remove product image",
    )
    assert len(product["images"]) == 1

    guest_checkout = expect(
        client.post(
            "/api/orders/guest-checkout",
            json={
                "email": f"qa-guest-{STAMP}@example.com",
                "full_name": "QA Guest",
                "phone": "0622334455",
                "address": "Guest Address 45",
                "city": "Rabat",
                "notes": "Guest checkout QA",
                "payment_method": "cash_on_delivery",
                "items": [{"product_id": product_id, "quantity": 1}],
            },
        ),
        201,
        "guest checkout without account",
    )
    guest_order = guest_checkout["order"]
    created["guest_order"] = guest_order["id"]
    assert guest_order["user_id"] is None
    assert guest_order["email"].startswith("qa-guest-")
    expect(
        client.post(
            "/api/orders/guest-track",
            json={
                "order_id": guest_order["id"],
                "tracking_token": guest_checkout["tracking_token"],
            },
        ),
        200,
        "guest tracks order with private token",
    )
    expect(
        client.post(
            "/api/orders/guest-track",
            json={
                "order_id": guest_order["id"],
                "tracking_token": "wrong-token-value-12345678901234567890",
            },
        ),
        404,
        "guest tracking rejects wrong token",
    )
    support_guest_orders = expect(
        client.get(
            "/api/support/orders?page_size=100",
            headers=support_headers,
        ),
        200,
        "support sees guest delivery details",
    )
    visible_guest = next(
        item
        for item in support_guest_orders["items"]
        if item["id"] == guest_order["id"]
    )
    assert visible_guest["phone"] == "0622334455"
    assert visible_guest["address"] == "Guest Address 45"
    expect(
        client.patch(
            f"/api/admin/orders/{guest_order['id']}/status",
            headers=admin_headers,
            json={"order_status": "cancelled"},
        ),
        200,
        "admin cancels temporary guest order",
    )

    customer = expect(
        client.post(
            "/api/auth/register",
            json={
                "email": CUSTOMER_EMAIL,
                "password": INITIAL_PASSWORD,
                "full_name": "QA Customer",
            },
        ),
        201,
        "register customer",
    )
    created["customer"] = customer["id"]
    customer_tokens = login(CUSTOMER_EMAIL, INITIAL_PASSWORD)
    customer_headers = bearer(customer_tokens["access_token"])

    verification = expect(
        client.post(
            "/api/auth/request-email-verification",
            headers=customer_headers,
        ),
        200,
        "request email verification",
    )
    assert verification["dev_token"]
    expect(
        client.post(
            "/api/auth/verify-email",
            json={"token": verification["dev_token"]},
        ),
        200,
        "verify customer email",
    )
    forgotten = expect(
        client.post(
            "/api/auth/forgot-password",
            json={"email": CUSTOMER_EMAIL},
        ),
        200,
        "forgot password",
    )
    assert forgotten["dev_token"]
    expect(
        client.post(
            "/api/auth/reset-password",
            json={
                "token": forgotten["dev_token"],
                "new_password": RESET_PASSWORD,
            },
        ),
        200,
        "reset password",
    )
    customer_tokens = login(CUSTOMER_EMAIL, RESET_PASSWORD)
    customer_headers = bearer(customer_tokens["access_token"])
    expect(
        client.get("/api/admin/dashboard", headers=customer_headers),
        403,
        "customer admin protection",
    )

    cart = expect(
        client.post(
            "/api/cart/items",
            headers=customer_headers,
            json={"product_id": product_id, "quantity": 2},
        ),
        200,
        "add product to cart",
    )
    assert cart["item_count"] == 2
    cart = expect(
        client.patch(
            f"/api/cart/items/{product_id}",
            headers=customer_headers,
            json={"quantity": 3},
        ),
        200,
        "update cart quantity",
    )
    assert cart["item_count"] == 3
    expect(client.get("/api/cart", headers=customer_headers), 200, "read cart")

    order = expect(
        client.post(
            "/api/orders/checkout",
            headers=customer_headers,
            json={
                "full_name": "QA Customer",
                "phone": "0612345678",
                "address": "QA Test Address 123",
                "city": "Casablanca",
                "notes": "Temporary automated QA order",
                "payment_method": "cash_on_delivery",
            },
        ),
        201,
        "COD checkout",
    )
    created["order"] = order["id"]
    assert order["payment_method"] == "cash_on_delivery"
    assert order["order_status"] == "pending"
    after_checkout = expect(
        client.get(f"/api/products/{product_id}"),
        200,
        "stock after checkout",
    )
    assert after_checkout["stock"] == 12
    expect(
        client.get("/api/orders", headers=customer_headers),
        200,
        "customer order list",
    )
    cancelled = expect(
        client.post(
            f"/api/orders/{order['id']}/cancel",
            headers=customer_headers,
        ),
        200,
        "customer cancels pending order",
    )
    assert cancelled["order_status"] == "cancelled"
    after_cancel = expect(
        client.get(f"/api/products/{product_id}"),
        200,
        "stock restored after cancellation",
    )
    assert after_cancel["stock"] == 15

    ticket = expect(
        client.post(
            "/api/tickets",
            headers=customer_headers,
            json={
                "subject": "QA demande produit",
                "category": "product",
                "message": "Test automatique du workflow support.",
                "order_id": order["id"],
            },
        ),
        201,
        "customer creates support ticket",
    )
    created["ticket"] = ticket["id"]
    ticket = expect(
        client.post(
            f"/api/support/tickets/{ticket['id']}/messages",
            headers=support_headers,
            json={"message": "Reponse QA du support."},
        ),
        200,
        "support replies to ticket",
    )
    ticket = expect(
        client.patch(
            f"/api/support/tickets/{ticket['id']}/priority",
            headers=support_headers,
            json={"priority": "urgent"},
        ),
        200,
        "support changes ticket priority",
    )
    ticket = expect(
        client.patch(
            f"/api/support/tickets/{ticket['id']}/status",
            headers=support_headers,
            json={"status": "resolved"},
        ),
        200,
        "support resolves ticket",
    )
    assert ticket["status"] == "resolved" and ticket["priority"] == "urgent"
    ticket = expect(
        client.post(
            f"/api/tickets/{ticket['id']}/messages",
            headers=customer_headers,
            json={"message": "Merci, nouvelle question QA."},
        ),
        200,
        "customer reopens resolved ticket",
    )
    assert ticket["status"] == "open"

    notifications = expect(
        client.get("/api/notifications", headers=customer_headers),
        200,
        "customer notifications",
    )
    if notifications["items"]:
        expect(
            client.patch(
                f"/api/notifications/{notifications['items'][0]['id']}/read",
                headers=customer_headers,
            ),
            204,
            "mark notification read",
        )

    audit = expect(
        client.get(
            "/api/admin/audit-logs",
            headers=admin_headers,
            params={"page_size": 100},
        ),
        200,
        "audit contains QA actions",
    )
    support_actions = [
        item
        for item in audit["items"]
        if item["actor_email"] == SUPPORT_EMAIL
        and item["action"] == "product.update"
    ]
    assert support_actions, "Support product update was not attributed by email"

    expect(
        client.delete(
            f"/api/admin/support-users/{support['id']}",
            headers=admin_headers,
        ),
        204,
        "soft delete support account",
    )
    support_list = expect(
        client.get(
            "/api/admin/support-users",
            headers=admin_headers,
            params={"page_size": 100},
        ),
        200,
        "deleted support hidden from list",
    )
    assert all(item["id"] != support["id"] for item in support_list["items"])
    expect(
        client.get("/api/support/dashboard", headers=support_headers),
        401,
        "deleted support session revoked",
    )

    print(
        {
            "status": "PASS",
            "checks": len(checks),
            "customer": CUSTOMER_EMAIL,
            "support": SUPPORT_EMAIL,
            "temporary_product": product_id,
        }
    )
finally:
    cleanup()
    client.close()
