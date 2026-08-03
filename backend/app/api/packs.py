from pathlib import Path
from typing import Annotated
from uuid import uuid4

from anyio import to_thread
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.repositories.operations import OperationsRepository
from app.schemas.pack import PackCreate, PackListResponse, PackResponse, PackUpdate
from app.services.pack import PackService


router = APIRouter(prefix="/packs", tags=["Packs"])
UPLOAD_DIRECTORY = Path("app/static/uploads/packs")
MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_IMAGES = 8
ALLOWED_IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def _valid_image(extension: str, content: bytes) -> bool:
    return bool(content) and {
        "jpg": content.startswith(b"\xff\xd8\xff"),
        "png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
    }.get(extension, False)


@router.get("", response_model=PackListResponse)
async def list_packs(
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> PackListResponse:
    return await PackService(session).list_public()


@router.get("/admin/manage", response_model=PackListResponse)
async def list_admin_packs(
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    search: Annotated[str | None, Query(max_length=120)] = None,
) -> PackListResponse:
    return await PackService(session).list_admin(search)


@router.post("/admin/manage", response_model=PackResponse, status_code=status.HTTP_201_CREATED)
async def create_pack(
    data: PackCreate,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> PackResponse:
    result = await PackService(session).create(data, created_by=admin.id)
    OperationsRepository(session).add_audit(
        actor_id=admin.id,
        actor_role=admin.role,
        action="pack.created",
        entity_type="pack",
        entity_id=result.id,
        details={"name": result.name, "products": [item.product.product_id for item in result.products]},
    )
    await session.commit()
    return result


@router.patch("/admin/manage/{pack_id}", response_model=PackResponse)
async def update_pack(
    pack_id: int,
    data: PackUpdate,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> PackResponse:
    result = await PackService(session).update(pack_id, data)
    OperationsRepository(session).add_audit(
        actor_id=admin.id,
        actor_role=admin.role,
        action="pack.updated",
        entity_type="pack",
        entity_id=pack_id,
        details={"fields": sorted(data.model_fields_set)},
    )
    await session.commit()
    return result


@router.post("/admin/manage/{pack_id}/images", response_model=PackResponse)
async def upload_pack_images(
    pack_id: int,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    files: Annotated[list[UploadFile], File()],
) -> PackResponse:
    if not files or len(files) > MAX_IMAGES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Selectionne entre 1 et 8 photos")
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    try:
        for upload in files:
            extension = ALLOWED_IMAGE_TYPES.get((upload.content_type or "").lower())
            content = await upload.read(MAX_IMAGE_SIZE + 1)
            if not extension or len(content) > MAX_IMAGE_SIZE or not _valid_image(extension, content):
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Photo invalide. JPG, PNG ou WebP, 5 MB maximum")
            filename = f"pack-{pack_id}-{uuid4().hex}.{extension}"
            target = UPLOAD_DIRECTORY / filename
            await to_thread.run_sync(target.write_bytes, content)
            saved.append(f"/static/uploads/packs/{filename}")
        result = await PackService(session).set_media(pack_id, saved)
        OperationsRepository(session).add_audit(
            actor_id=admin.id,
            actor_role=admin.role,
            action="pack.images_added",
            entity_type="pack",
            entity_id=pack_id,
            details={"count": len(saved)},
        )
        await session.commit()
        return result
    except Exception:
        for url in saved:
            target = UPLOAD_DIRECTORY / Path(url).name
            if target.exists():
                await to_thread.run_sync(target.unlink)
        raise


@router.post("/admin/manage/{pack_id}/cover", response_model=PackResponse)
async def upload_pack_cover(
    pack_id: int,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    file: Annotated[UploadFile, File()],
) -> PackResponse:
    extension = ALLOWED_IMAGE_TYPES.get((file.content_type or "").lower())
    content = await file.read(MAX_IMAGE_SIZE + 1)
    if not extension or len(content) > MAX_IMAGE_SIZE or not _valid_image(extension, content):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Photo invalide. JPG, PNG ou WebP, 5 MB maximum",
        )

    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    filename = f"pack-{pack_id}-cover-{uuid4().hex}.{extension}"
    target = UPLOAD_DIRECTORY / filename
    image_url = f"/static/uploads/packs/{filename}"
    try:
        await to_thread.run_sync(target.write_bytes, content)
        result = await PackService(session).set_main_image(pack_id, image_url)
        OperationsRepository(session).add_audit(
            actor_id=admin.id,
            actor_role=admin.role,
            action="pack.cover_updated",
            entity_type="pack",
            entity_id=pack_id,
            details={"image_url": image_url},
        )
        await session.commit()
        return result
    except Exception:
        if target.exists():
            await to_thread.run_sync(target.unlink)
        raise


@router.patch("/admin/manage/{pack_id}/main-image", response_model=PackResponse)
async def set_pack_main_image(
    pack_id: int,
    image_url: Annotated[str, Query(min_length=1, max_length=1000)],
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> PackResponse:
    result = await PackService(session).set_main_image(pack_id, image_url)
    await session.commit()
    return result


@router.delete("/admin/manage/{pack_id}/images", response_model=PackResponse)
async def remove_pack_image(
    pack_id: int,
    image_url: Annotated[str, Query(min_length=1, max_length=1000)],
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> PackResponse:
    result = await PackService(session).remove_image(pack_id, image_url)
    await session.commit()
    if image_url.startswith("/static/uploads/packs/"):
        target = (UPLOAD_DIRECTORY / Path(image_url).name).resolve()
        if target.parent == UPLOAD_DIRECTORY.resolve() and target.exists():
            await to_thread.run_sync(target.unlink)
    return result


@router.delete("/admin/manage/{pack_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pack(
    pack_id: int,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> Response:
    await PackService(session).delete(pack_id)
    OperationsRepository(session).add_audit(
        actor_id=admin.id, actor_role=admin.role, action="pack.deleted", entity_type="pack", entity_id=pack_id
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{pack_id}", response_model=PackResponse)
async def get_pack(
    pack_id: int,
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> PackResponse:
    return await PackService(session).get(pack_id, public=True)
