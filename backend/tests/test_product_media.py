from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.api.products import upload_product_media
from app.models.user import User
from app.schemas.product import ProductResponse


def make_user(role: str = "admin") -> User:
    return User(
        id=1,
        email=f"{role}@example.com",
        hashed_password="test",
        role=role,
        token_version=1,
        is_active=True,
    )


def upload(filename: str, content_type: str, content: bytes) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=BytesIO(content),
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.asyncio
@patch("app.api.products.OperationsRepository")
@patch("app.api.products.product_service")
async def test_staff_can_upload_multiple_images_and_video(
    service: MagicMock,
    operations: MagicMock,
    tmp_path,
) -> None:
    current = ProductResponse(product_id=42, images=[], videos=[])
    updated = ProductResponse(
        product_id=42,
        images=["/static/uploads/products/42-a.png"],
        videos=["/static/uploads/products/42-b.mp4"],
    )
    service.get_product = AsyncMock(return_value=current)
    service.update_product = AsyncMock(return_value=updated)
    session = AsyncMock()
    png = b"\x89PNG\r\n\x1a\nvalid-image"
    mp4 = b"\x00\x00\x00\x18ftypisomvalid-video"

    with patch("app.api.products.UPLOAD_DIRECTORY", tmp_path):
        result = await upload_product_media(
            42,
            make_user("support"),
            session,
            [
                upload("front.png", "image/png", png),
                upload("demo.mp4", "video/mp4", mp4),
            ],
        )

    assert result.videos == updated.videos
    assert service.update_product.await_args.args[1].images[0].endswith(".png")
    assert service.update_product.await_args.args[1].videos[0].endswith(".mp4")
    assert len(list(tmp_path.iterdir())) == 2
    operations.return_value.add_audit.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.api.products.product_service")
async def test_media_upload_rejects_fake_video_and_cleans_files(
    service: MagicMock,
    tmp_path,
) -> None:
    service.get_product = AsyncMock(
        return_value=ProductResponse(product_id=42, images=[], videos=[])
    )
    service.update_product = AsyncMock()

    with (
        patch("app.api.products.UPLOAD_DIRECTORY", tmp_path),
        pytest.raises(HTTPException) as error,
    ):
        await upload_product_media(
            42,
            make_user(),
            AsyncMock(),
            [upload("fake.mp4", "video/mp4", b"this-is-not-an-mp4")],
        )

    assert error.value.status_code == 415
    assert list(tmp_path.iterdir()) == []
    service.update_product.assert_not_awaited()


@pytest.mark.asyncio
@patch("app.api.products.product_service")
async def test_media_upload_enforces_product_video_limit(
    service: MagicMock,
    tmp_path,
) -> None:
    service.get_product = AsyncMock(
        return_value=ProductResponse(
            product_id=42,
            videos=[f"/video-{index}.mp4" for index in range(4)],
        )
    )

    with (
        patch("app.api.products.UPLOAD_DIRECTORY", tmp_path),
        pytest.raises(HTTPException) as error,
    ):
        await upload_product_media(
            42,
            make_user(),
            AsyncMock(),
            [
                upload(
                    "extra.mp4",
                    "video/mp4",
                    b"\x00\x00\x00\x18ftypisomextra",
                )
            ],
        )

    assert error.value.status_code == 400
    assert "4 videos" in str(error.value.detail)
