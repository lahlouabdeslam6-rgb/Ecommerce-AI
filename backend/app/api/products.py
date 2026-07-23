from pathlib import Path
from typing import Annotated
from uuid import uuid4

from anyio import to_thread
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.repositories.operations import OperationsRepository
from app.schemas.product import (
    ProductCreate,
    ProductListResponse,
    ProductImagesOrder,
    ProductResponse,
    ProductStockUpdate,
    ProductUpdate,
)
from app.services.product import ProductService
from app.services.product_agent import ProductAgentService


router = APIRouter(prefix="/products", tags=["Products"])
product_service = ProductService()
UPLOAD_DIRECTORY = Path("app/static/uploads/products")
MAX_IMAGE_SIZE = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    brand: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    ingredient: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    category: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    flavor: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    in_stock: bool | None = None,
    sort_by: Annotated[
        str,
        Query(pattern=r"^(newest|name|price_asc|price_desc|stock_desc)$"),
    ] = "newest",
) -> ProductListResponse:
    return await product_service.list_products(
        page=page,
        page_size=page_size,
        search=search,
        brand=brand,
        ingredient=ingredient,
        category=category,
        flavor=flavor,
        min_price=min_price,
        max_price=max_price,
        in_stock=in_stock,
        sort_by=sort_by,
    )


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    user: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> ProductResponse:
    product = await product_service.create_product(data)
    OperationsRepository(session).add_audit(
        actor_id=user.id,
        actor_role=user.role,
        action="product.create",
        entity_type="product",
        entity_id=product.product_id,
        details={"name": product.name, "stock": product.stock, "price": product.price},
    )
    await session.commit()
    return product


@router.get("/filters", response_model=dict[str, list[str]])
async def catalog_filters() -> dict[str, list[str]]:
    return await product_service.catalog_filters()


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int) -> ProductResponse:
    return await product_service.get_product(product_id)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    data: ProductUpdate,
    user: Annotated[User, Depends(require_roles("admin", "support"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> ProductResponse:
    before = await product_service.get_product(product_id)
    product = await product_service.update_product(product_id, data)
    operations = OperationsRepository(session)
    changes = {
        field: {"before": getattr(before, field), "after": getattr(product, field)}
        for field in data.model_fields_set
        if getattr(before, field) != getattr(product, field)
    }
    operations.add_audit(
        actor_id=user.id,
        actor_role=user.role,
        action="product.update",
        entity_type="product",
        entity_id=product_id,
        details={"changes": changes},
    )
    if before.stock != product.stock:
        operations.add_stock_movement(
            product_id=product_id,
            product_name=product.name or "Produit",
            movement_type="manual_adjustment",
            quantity=product.stock - before.stock,
            stock_before=before.stock,
            stock_after=product.stock,
            actor_id=user.id,
            note="Modification depuis la fiche produit",
        )
    if product.stock <= 5:
        for role in ("admin", "support"):
            operations.add_notification(
                target_role=role,
                notification_type="low_stock",
                title="Stock faible",
                message=f"{product.name or 'Produit'}: {product.stock} unite(s).",
                link=(
                    f"/admin?product={product_id}"
                    if role == "admin"
                    else f"/support/products/{product_id}"
                ),
            )
    await session.commit()
    return product


@router.patch("/{product_id}/stock", response_model=ProductResponse)
async def update_product_stock(
    product_id: int,
    data: ProductStockUpdate,
    user: Annotated[User, Depends(require_roles("admin", "support"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> ProductResponse:
    before = await product_service.get_product(product_id)
    product = await product_service.update_stock(product_id, data.stock)
    operations = OperationsRepository(session)
    operations.add_stock_movement(
        product_id=product_id,
        product_name=product.name or "Produit",
        movement_type="manual_adjustment",
        quantity=product.stock - before.stock,
        stock_before=before.stock,
        stock_after=product.stock,
        actor_id=user.id,
        note="Correction manuelle du stock",
    )
    operations.add_audit(
        actor_id=user.id,
        actor_role=user.role,
        action="stock.update",
        entity_type="product",
        entity_id=product_id,
        details={"before": before.stock, "after": product.stock},
    )
    await session.commit()
    return product


@router.post("/{product_id}/images", response_model=ProductResponse)
async def upload_product_image(
    product_id: int,
    user: Annotated[User, Depends(require_roles("admin", "support"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    image: Annotated[UploadFile, File(description="JPEG, PNG or WebP; max 5 MB")],
) -> ProductResponse:
    extension = ALLOWED_IMAGE_TYPES.get(image.content_type or "")
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG and WebP images are allowed",
        )

    await product_service.get_product(product_id)
    content = await image.read(MAX_IMAGE_SIZE + 1)
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Image must not exceed 5 MB",
        )
    signatures_valid = {
        "jpg": content.startswith(b"\xff\xd8\xff"),
        "png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
    }
    if not content or not signatures_valid[extension]:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Image content does not match its declared type",
        )

    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    filename = f"{product_id}-{uuid4().hex}.{extension}"
    target = UPLOAD_DIRECTORY / filename
    await to_thread.run_sync(target.write_bytes, content)
    image_url = f"/static/uploads/products/{filename}"
    product = await product_service.add_image(product_id, image_url)
    OperationsRepository(session).add_audit(
        actor_id=user.id,
        actor_role=user.role,
        action="product.image.add",
        entity_type="product",
        entity_id=product_id,
        details={"image_url": image_url},
    )
    await session.commit()
    return product


@router.patch("/{product_id}/images/order", response_model=ProductResponse)
async def reorder_product_images(
    product_id: int,
    data: ProductImagesOrder,
    user: Annotated[User, Depends(require_roles("admin", "support"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> ProductResponse:
    current = await product_service.get_product(product_id)
    if set(data.images) != set(current.images):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "The complete current image list is required",
        )
    product = await product_service.set_images(product_id, data.images)
    OperationsRepository(session).add_audit(
        actor_id=user.id,
        actor_role=user.role,
        action="product.images.reordered",
        entity_type="product",
        entity_id=product_id,
    )
    await session.commit()
    return product


@router.delete("/{product_id}/images", response_model=ProductResponse)
async def remove_product_image(
    product_id: int,
    image_url: Annotated[str, Query(min_length=1, max_length=500)],
    user: Annotated[User, Depends(require_roles("admin", "support"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> ProductResponse:
    current = await product_service.get_product(product_id)
    if image_url not in current.images:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Image not found")
    product = await product_service.set_images(
        product_id, [item for item in current.images if item != image_url]
    )
    local_prefix = "/static/uploads/products/"
    if image_url.startswith(local_prefix):
        filename = Path(image_url).name
        target = (UPLOAD_DIRECTORY / filename).resolve()
        upload_root = UPLOAD_DIRECTORY.resolve()
        if target.parent == upload_root and target.exists():
            await to_thread.run_sync(target.unlink)
    OperationsRepository(session).add_audit(
        actor_id=user.id,
        actor_role=user.role,
        action="product.image.removed",
        entity_type="product",
        entity_id=product_id,
        details={"image_url": image_url},
    )
    await session.commit()
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    user: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> Response:
    product = await product_service.get_product(product_id)
    await product_service.delete_product(product_id)
    await ProductAgentService().remove_product_index(product_id)
    OperationsRepository(session).add_audit(
        actor_id=user.id,
        actor_role=user.role,
        action="product.delete",
        entity_type="product",
        entity_id=product_id,
        details={"name": product.name},
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
