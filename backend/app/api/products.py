from datetime import UTC, datetime, timedelta
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
from app.repositories.analytics import AnalyticsRepository
from app.repositories.operations import OperationsRepository
from app.repositories.promotion_signals import PromotionSignalsRepository
from app.schemas.product import (
    ProductCostResponse,
    ProductCostUpdate,
    ProductCreate,
    ProductListResponse,
    ProductImagesOrder,
    ProductResponse,
    ProductStockUpdate,
    ProductUpdate,
    ProductVideosOrder,
)
from app.services.product import ProductService
from app.services.product_agent import ProductAgentService


router = APIRouter(prefix="/products", tags=["Products"])
product_service = ProductService()
UPLOAD_DIRECTORY = Path("app/static/uploads/products")
MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_VIDEO_SIZE = 50 * 1024 * 1024
MAX_MEDIA_FILES_PER_UPLOAD = 8
MAX_PRODUCT_IMAGES = 12
MAX_PRODUCT_VIDEOS = 4
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
ALLOWED_VIDEO_TYPES = {
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/quicktime": "mov",
    "video/x-m4v": "m4v",
}


def _valid_media_signature(extension: str, content: bytes) -> bool:
    checks = {
        "jpg": content.startswith(b"\xff\xd8\xff"),
        "png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
        "mp4": len(content) >= 12 and content[4:8] == b"ftyp",
        "mov": len(content) >= 12 and content[4:8] == b"ftyp",
        "m4v": len(content) >= 12 and content[4:8] == b"ftyp",
        "webm": content.startswith(b"\x1aE\xdf\xa3"),
    }
    return bool(content) and checks.get(extension, False)


async def _unlink_local_asset(asset_url: str) -> None:
    local_prefix = "/static/uploads/products/"
    if not asset_url.startswith(local_prefix):
        return
    target = (UPLOAD_DIRECTORY / Path(asset_url).name).resolve()
    upload_root = UPLOAD_DIRECTORY.resolve()
    if target.parent == upload_root and target.exists():
        await to_thread.run_sync(target.unlink)


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


@router.get("/best-sellers", response_model=list[ProductResponse])
async def best_sellers(
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    limit: Annotated[int, Query(ge=4, le=20)] = 10,
) -> list[ProductResponse]:
    end = datetime.now(UTC)
    sales = await AnalyticsRepository(session).top_products(
        end - timedelta(days=3650),
        end,
        limit=limit,
    )
    products = await product_service.get_products(
        [int(item["product_id"]) for item in sales]
    )
    if products:
        return products
    fallback = await product_service.list_products(
        page=1,
        page_size=limit,
        search=None,
        brand=None,
        ingredient=None,
        category=None,
        flavor=None,
        min_price=None,
        max_price=None,
        in_stock=True,
        sort_by="stock_desc",
    )
    return fallback.items


@router.get("/manage", response_model=ProductListResponse)
async def manage_products(
    _: Annotated[User, Depends(require_roles("admin", "support"))],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    search: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
) -> ProductListResponse:
    return await product_service.list_products(
        page=page,
        page_size=page_size,
        search=search,
        brand=None,
        ingredient=None,
        category=None,
        flavor=None,
        min_price=None,
        max_price=None,
        in_stock=None,
        sort_by="newest",
        active_only=False,
    )


@router.get("/costs/{product_id}", response_model=ProductCostResponse)
async def get_product_cost(
    product_id: int,
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> ProductCostResponse:
    await product_service.get_product(product_id)
    cost = await PromotionSignalsRepository(session).get_cost(product_id)
    return ProductCostResponse(
        product_id=product_id,
        cost_price=float(cost.cost_price) if cost else None,
        currency=cost.currency if cost else "MAD",
    )


@router.put("/costs/{product_id}", response_model=ProductCostResponse)
async def update_product_cost(
    product_id: int,
    data: ProductCostUpdate,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> ProductCostResponse:
    await product_service.get_product(product_id)
    cost = await PromotionSignalsRepository(session).upsert_cost(
        product_id=product_id,
        cost_price=data.cost_price,
        currency=data.currency.upper(),
        updated_by=admin.id,
    )
    OperationsRepository(session).add_audit(
        actor_id=admin.id,
        actor_role=admin.role,
        action="product.cost.updated",
        entity_type="product",
        entity_id=product_id,
        details={"currency": cost.currency},
    )
    await session.commit()
    return ProductCostResponse(
        product_id=product_id,
        cost_price=float(cost.cost_price),
        currency=cost.currency,
    )


@router.post("/{product_id}/view", status_code=status.HTTP_204_NO_CONTENT)
async def record_product_view(
    product_id: int,
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> Response:
    await product_service.get_product(product_id)
    PromotionSignalsRepository(session).add_view(product_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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

    current = await product_service.get_product(product_id)
    if len(current.images) >= MAX_PRODUCT_IMAGES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"A product cannot have more than {MAX_PRODUCT_IMAGES} images",
        )
    content = await image.read(MAX_IMAGE_SIZE + 1)
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Image must not exceed 5 MB",
        )
    if not _valid_media_signature(extension, content):
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


@router.post("/{product_id}/media", response_model=ProductResponse)
async def upload_product_media(
    product_id: int,
    user: Annotated[User, Depends(require_roles("admin", "support"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    files: Annotated[
        list[UploadFile],
        File(
            description=(
                "Up to 8 JPEG, PNG, WebP, MP4, WebM, MOV or M4V files. "
                "Images max 5 MB; videos max 50 MB."
            )
        ),
    ],
) -> ProductResponse:
    if not files or len(files) > MAX_MEDIA_FILES_PER_UPLOAD:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Select between 1 and {MAX_MEDIA_FILES_PER_UPLOAD} files",
        )

    current = await product_service.get_product(product_id)
    definitions: list[tuple[UploadFile, str, str, int]] = []
    image_count = 0
    video_count = 0
    for media in files:
        content_type = media.content_type or ""
        if content_type in ALLOWED_IMAGE_TYPES:
            definitions.append(
                (media, "image", ALLOWED_IMAGE_TYPES[content_type], MAX_IMAGE_SIZE)
            )
            image_count += 1
        elif content_type in ALLOWED_VIDEO_TYPES:
            definitions.append(
                (media, "video", ALLOWED_VIDEO_TYPES[content_type], MAX_VIDEO_SIZE)
            )
            video_count += 1
        else:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "Only JPEG, PNG, WebP, MP4, WebM, MOV and M4V files are allowed",
            )

    if len(current.images) + image_count > MAX_PRODUCT_IMAGES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"A product cannot have more than {MAX_PRODUCT_IMAGES} images",
        )
    if len(current.videos) + video_count > MAX_PRODUCT_VIDEOS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"A product cannot have more than {MAX_PRODUCT_VIDEOS} videos",
        )

    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    created_urls: list[str] = []
    image_urls: list[str] = []
    video_urls: list[str] = []
    try:
        for media, media_kind, extension, size_limit in definitions:
            content = await media.read(size_limit + 1)
            if len(content) > size_limit:
                label = "Image" if media_kind == "image" else "Video"
                limit_mb = size_limit // (1024 * 1024)
                raise HTTPException(
                    status.HTTP_413_CONTENT_TOO_LARGE,
                    f"{label} must not exceed {limit_mb} MB",
                )
            if not _valid_media_signature(extension, content):
                raise HTTPException(
                    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    "Media content does not match its declared type",
                )
            filename = f"{product_id}-{uuid4().hex}.{extension}"
            target = UPLOAD_DIRECTORY / filename
            await to_thread.run_sync(target.write_bytes, content)
            asset_url = f"/static/uploads/products/{filename}"
            created_urls.append(asset_url)
            if media_kind == "image":
                image_urls.append(asset_url)
            else:
                video_urls.append(asset_url)

        product = await product_service.update_product(
            product_id,
            ProductUpdate(
                images=[*current.images, *image_urls],
                videos=[*current.videos, *video_urls],
            ),
        )
    except Exception:
        for asset_url in created_urls:
            await _unlink_local_asset(asset_url)
        raise

    OperationsRepository(session).add_audit(
        actor_id=user.id,
        actor_role=user.role,
        action="product.media.add",
        entity_type="product",
        entity_id=product_id,
        details={"images": image_urls, "videos": video_urls},
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


@router.patch("/{product_id}/videos/order", response_model=ProductResponse)
async def reorder_product_videos(
    product_id: int,
    data: ProductVideosOrder,
    user: Annotated[User, Depends(require_roles("admin", "support"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> ProductResponse:
    current = await product_service.get_product(product_id)
    if set(data.videos) != set(current.videos):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "The complete current video list is required",
        )
    product = await product_service.set_videos(product_id, data.videos)
    OperationsRepository(session).add_audit(
        actor_id=user.id,
        actor_role=user.role,
        action="product.videos.reordered",
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
    await _unlink_local_asset(image_url)
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


@router.delete("/{product_id}/videos", response_model=ProductResponse)
async def remove_product_video(
    product_id: int,
    video_url: Annotated[str, Query(min_length=1, max_length=500)],
    user: Annotated[User, Depends(require_roles("admin", "support"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> ProductResponse:
    current = await product_service.get_product(product_id)
    if video_url not in current.videos:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Video not found")
    product = await product_service.set_videos(
        product_id, [item for item in current.videos if item != video_url]
    )
    await _unlink_local_asset(video_url)
    OperationsRepository(session).add_audit(
        actor_id=user.id,
        actor_role=user.role,
        action="product.video.removed",
        entity_type="product",
        entity_id=product_id,
        details={"video_url": video_url},
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
