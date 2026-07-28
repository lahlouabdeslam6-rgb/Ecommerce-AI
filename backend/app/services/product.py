from fastapi import HTTPException, status

from app.repositories.product import ProductRepository
from app.schemas.product import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)


class ProductService:
    def __init__(self, repository: ProductRepository | None = None) -> None:
        self.repository = repository or ProductRepository()

    async def list_products(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        brand: str | None,
        ingredient: str | None,
        category: str | None,
        flavor: str | None,
        min_price: float | None,
        max_price: float | None,
        in_stock: bool | None,
        sort_by: str = "newest",
        active_only: bool = True,
    ) -> ProductListResponse:
        skip = (page - 1) * page_size
        products, total = await self.repository.list_products(
            skip=skip,
            limit=page_size,
            search=search,
            brand=brand,
            ingredient=ingredient,
            category=category,
            flavor=flavor,
            min_price=min_price,
            max_price=max_price,
            in_stock=in_stock,
            sort_by=sort_by,
            active_only=active_only,
        )
        total_pages = (total + page_size - 1) // page_size
        return ProductListResponse(
            items=[ProductResponse.model_validate(product) for product in products],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_product(self, product_id: int) -> ProductResponse:
        product = await self.repository.get_by_product_id(product_id)
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )
        return ProductResponse.model_validate(product)

    async def catalog_filters(self) -> dict[str, list[str]]:
        return await self.repository.catalog_filters()

    async def create_product(self, data: ProductCreate) -> ProductResponse:
        product_data = data.model_dump(mode="json")
        product = await self.repository.create_product(product_data)
        return ProductResponse.model_validate(product)

    async def update_product(
        self,
        product_id: int,
        data: ProductUpdate,
    ) -> ProductResponse:
        updates = data.model_dump(exclude_unset=True, mode="json")
        if not updates:
            return await self.get_product(product_id)
        product = await self.repository.update_product(product_id, updates)
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )
        return ProductResponse.model_validate(product)

    async def update_stock(self, product_id: int, stock: int) -> ProductResponse:
        product = await self.repository.update_stock(product_id, stock)
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )
        return ProductResponse.model_validate(product)

    async def add_image(self, product_id: int, image_url: str) -> ProductResponse:
        product = await self.repository.add_image(product_id, image_url)
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )
        return ProductResponse.model_validate(product)

    async def set_images(
        self, product_id: int, images: list[str]
    ) -> ProductResponse:
        current = await self.get_product(product_id)
        if len(images) != len(set(images)):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Duplicate image URL")
        if not set(images).issubset(set(current.images)):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Images must already belong to this product",
            )
        product = await self.repository.set_images(product_id, images)
        if product is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
        return ProductResponse.model_validate(product)

    async def set_videos(
        self, product_id: int, videos: list[str]
    ) -> ProductResponse:
        current = await self.get_product(product_id)
        if len(videos) != len(set(videos)):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Duplicate video URL")
        if not set(videos).issubset(set(current.videos)):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Videos must already belong to this product",
            )
        product = await self.repository.set_videos(product_id, videos)
        if product is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
        return ProductResponse.model_validate(product)

    async def delete_product(self, product_id: int) -> None:
        if not await self.repository.delete_product(product_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )
