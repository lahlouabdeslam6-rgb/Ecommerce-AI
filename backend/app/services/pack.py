import json
import re
import unicodedata
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pack import Pack
from app.repositories.pack import PackRepository
from app.repositories.marketing import MarketingRepository
from app.repositories.product import ProductRepository
from app.repositories.promotion_signals import PromotionSignalsRepository
from app.schemas.pack import PackCreate, PackListResponse, PackProductResponse, PackResponse, PackUpdate
from app.schemas.product import ProductResponse


class PackService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = PackRepository(session)
        self.products = ProductRepository()
        self.promotion_signals = PromotionSignalsRepository(session)

    async def list_public(self) -> PackListResponse:
        await self._expire_due()
        packs = await self.repository.list_public(datetime.now(UTC))
        responses = [await self._response(pack) for pack in packs]
        responses = [item for item in responses if item.is_available]
        return PackListResponse(items=responses, total=len(responses))

    async def list_admin(self, search: str | None = None) -> PackListResponse:
        await self._expire_due()
        packs = await self.repository.list_admin(search)
        responses = [await self._response(pack) for pack in packs]
        return PackListResponse(items=responses, total=len(responses))

    async def get(self, pack_id: int, *, public: bool = False) -> PackResponse:
        pack = await self._get(pack_id)
        response = await self._response(pack)
        if public and (not response.is_active or not response.is_available):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Pack introuvable")
        return response

    async def create(self, data: PackCreate, *, created_by: int | None, source: str = "admin", campaign_id: int | None = None) -> PackResponse:
        products, regular_price, cost_price = await self._validate_items(data.items)
        slug = await self._unique_slug(data.name)
        promotional_price = self._price(
            regular_price, data.discount_percentage, data.promotional_price
        )
        self._validate_margin(promotional_price, cost_price)
        description = data.description.strip() or self._default_description(products, data.items)
        pack = await self.repository.create(
            {
                "name": data.name.strip(),
                "slug": slug,
                "description": description,
                "highlights": [item.strip() for item in data.highlights if item.strip()],
                "main_image_url": None,
                "gallery": [],
                "regular_price": regular_price,
                "discount_percentage": data.discount_percentage,
                "promotional_price": promotional_price,
                "currency": "MAD",
                "is_active": data.is_active,
                "source": source,
                "campaign_id": campaign_id,
                "created_by": created_by,
                "starts_at": data.starts_at,
                "ends_at": data.ends_at,
            },
            [item.model_dump() for item in data.items],
        )
        return await self._response(pack)

    async def update(self, pack_id: int, data: PackUpdate) -> PackResponse:
        pack = await self._get(pack_id)
        values = data.model_dump(exclude_unset=True, exclude={"items"}, mode="python")
        items = data.items
        source_items = items or [
            type("PackItemValue", (), {"product_id": item.product_id, "quantity": item.quantity})()
            for item in pack.items
        ]
        products, regular_price, cost_price = await self._validate_items(source_items)
        discount = float(values.get("discount_percentage", pack.discount_percentage))
        explicit_price = values.pop("promotional_price", None)
        values["regular_price"] = regular_price
        values["promotional_price"] = self._price(regular_price, discount, explicit_price)
        self._validate_margin(values["promotional_price"], cost_price)
        if "name" in values:
            values["name"] = str(values["name"]).strip()
            values["slug"] = await self._unique_slug(values["name"], exclude_id=pack.id)
        if "description" in values:
            values["description"] = str(values["description"]).strip() or self._default_description(products, source_items)
        updated = await self.repository.update(
            pack,
            values,
            [item.model_dump() for item in items] if items is not None else None,
        )
        return await self._response(updated)

    async def set_media(self, pack_id: int, urls: list[str]) -> PackResponse:
        pack = await self._get(pack_id)
        gallery = list(dict.fromkeys([*json.loads(pack.gallery_json or "[]"), *urls]))[:12]
        updated = await self.repository.update(
            pack,
            {"gallery": gallery, "main_image_url": pack.main_image_url or gallery[0]},
        )
        return await self._response(updated)

    async def set_main_image(self, pack_id: int, image_url: str) -> PackResponse:
        pack = await self._get(pack_id)
        gallery = list(dict.fromkeys([image_url, *json.loads(pack.gallery_json or "[]")]))[:12]
        updated = await self.repository.update(
            pack, {"main_image_url": image_url, "gallery": gallery}
        )
        return await self._response(updated)

    async def remove_image(self, pack_id: int, image_url: str) -> PackResponse:
        pack = await self._get(pack_id)
        gallery = [item for item in json.loads(pack.gallery_json or "[]") if item != image_url]
        updated = await self.repository.update(
            pack,
            {"gallery": gallery, "main_image_url": gallery[0] if pack.main_image_url == image_url and gallery else None},
        )
        return await self._response(updated)

    async def delete(self, pack_id: int) -> None:
        await self.repository.delete(await self._get(pack_id))

    async def sync_marketing_campaign(self, campaign, *, created_by: int) -> PackResponse | None:
        if campaign.campaign_type != "promotion" or campaign.promotion_kind != "pack":
            return None
        item_ids = campaign.product_ids or ([campaign.product_id] if campaign.product_id else [])
        data = PackCreate(
            name=campaign.campaign_title,
            description=campaign.core_message,
            highlights=[campaign.headline],
            items=[{"product_id": value, "quantity": 1} for value in item_ids],
            discount_percentage=float(campaign.discount_percentage or 0),
            is_active=True,
            starts_at=campaign.starts_at,
            ends_at=campaign.ends_at,
        )
        existing = await self.repository.get_by_campaign(campaign.id)
        if existing:
            result = await self.update(existing.id, PackUpdate(**data.model_dump()))
        else:
            result = await self.create(
                data,
                created_by=created_by,
                source="marketing",
                campaign_id=campaign.id,
            )
        if campaign.pack_cover_image_url:
            result = await self.set_main_image(
                result.id,
                campaign.pack_cover_image_url,
            )
        return result

    async def sync_approved_marketing_packs(self) -> int:
        campaigns = await MarketingRepository(self.session).active_promotions(
            now=datetime.now(UTC)
        )
        synced = 0
        for campaign in campaigns:
            if campaign.promotion_kind != "pack":
                continue
            product_ids = campaign.product_ids or (
                [campaign.product_id] if campaign.product_id else []
            )
            if len(product_ids) < 2 or await self.repository.get_by_campaign(campaign.id):
                continue
            await self.sync_marketing_campaign(
                campaign,
                created_by=campaign.approved_by or campaign.created_by,
            )
            synced += 1
        if synced:
            await self.session.commit()
        return synced

    async def deactivate_campaign_pack(self, campaign_id: int) -> None:
        pack = await self.repository.get_by_campaign(campaign_id)
        if pack is not None and pack.is_active:
            await self.repository.update(pack, {"is_active": False})

    async def _get(self, pack_id: int) -> Pack:
        pack = await self.repository.get(pack_id)
        if pack is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Pack introuvable")
        return pack

    async def _validate_items(self, items) -> tuple[dict[int, dict], float, float | None]:
        product_ids = [int(item.product_id) for item in items]
        products = await self.products.get_many_by_ids(product_ids)
        if len(products) != len(set(product_ids)):
            raise HTTPException(status.HTTP_409_CONFLICT, "Un produit du pack est introuvable")
        total = 0.0
        costs = await self.promotion_signals.cost_map(product_ids)
        total_cost = 0.0
        has_all_costs = len(costs) == len(set(product_ids))
        for item in items:
            product = products[int(item.product_id)]
            if not product.get("is_active") or product.get("price") is None:
                raise HTTPException(status.HTTP_409_CONFLICT, f"Produit {item.product_id} indisponible")
            total += float(product["price"]) * int(item.quantity)
            if has_all_costs:
                total_cost += costs[int(item.product_id)] * int(item.quantity)
        return products, round(total, 2), round(total_cost, 2) if has_all_costs else None

    async def _expire_due(self) -> None:
        if await self.repository.expire_due(datetime.now(UTC)):
            await self.session.commit()

    @staticmethod
    def _validate_margin(promotional_price: float, total_cost: float | None) -> None:
        if total_cost is not None and promotional_price < total_cost:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Le prix promo ne peut pas etre inferieur au cout d'achat ({total_cost:.2f} MAD)",
            )

    async def _response(self, pack: Pack) -> PackResponse:
        product_ids = [item.product_id for item in pack.items]
        products = await self.products.get_many_by_ids(product_ids)
        response_products: list[PackProductResponse] = []
        stocks: list[int] = []
        for item in sorted(pack.items, key=lambda value: value.position):
            product = products.get(item.product_id)
            if product is None:
                continue
            response_products.append(
                PackProductResponse(
                    product=ProductResponse.model_validate(product), quantity=item.quantity
                )
            )
            stocks.append(int(product.get("stock") or 0) // item.quantity)
        now = datetime.now(UTC)
        starts_ok = pack.starts_at is None or self._as_utc(pack.starts_at) <= now
        ends_ok = pack.ends_at is None or self._as_utc(pack.ends_at) >= now
        stock = min(stocks) if stocks and len(response_products) == len(pack.items) else 0
        gallery = json.loads(pack.gallery_json or "[]")
        main_image_url = pack.main_image_url
        description = pack.description
        if main_image_url and not gallery:
            product_images = {
                image
                for product in products.values()
                for image in product.get("images", [])
            }
            if main_image_url in product_images:
                main_image_url = None
                description = self._default_description(products, pack.items)

        return PackResponse(
            id=pack.id,
            name=pack.name,
            slug=pack.slug,
            description=description,
            highlights=json.loads(pack.highlights_json or "[]"),
            main_image_url=main_image_url,
            gallery=gallery,
            products=response_products,
            regular_price=round(pack.regular_price, 2),
            discount_percentage=round(pack.discount_percentage, 2),
            promotional_price=round(pack.promotional_price, 2),
            currency=pack.currency,
            stock=stock,
            is_available=bool(pack.is_active and starts_ok and ends_ok and stock > 0),
            is_active=pack.is_active,
            source=pack.source,
            campaign_id=pack.campaign_id,
            starts_at=pack.starts_at,
            ends_at=pack.ends_at,
            created_at=pack.created_at,
            updated_at=pack.updated_at,
        )

    @staticmethod
    def _price(regular: float, discount: float, explicit: float | None) -> float:
        value = explicit if explicit is not None else regular * (1 - discount / 100)
        if value > regular:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Le prix promo depasse le prix normal")
        return round(value, 2)

    @staticmethod
    def _default_description(products: dict[int, dict], items) -> str:
        names = [
            str(products[int(item.product_id)].get("name") or f"Produit #{item.product_id}")
            for item in items
            if int(item.product_id) in products
        ]
        visible = names[:4]
        if len(visible) > 1:
            selection = ", ".join(visible[:-1]) + f" et {visible[-1]}"
        else:
            selection = visible[0] if visible else "plusieurs produits selectionnes"
        if len(names) > len(visible):
            selection += f", ainsi que {len(names) - len(visible)} autre(s) produit(s)"
        return f"Ce pack NUTRIFIT reunit {selection} dans une offre groupee simple et avantageuse."

    async def _unique_slug(self, value: str, *, exclude_id: int | None = None) -> str:
        normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
        base = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-") or "pack"
        slug = base
        suffix = 2
        while await self.repository.slug_exists(slug, exclude_id=exclude_id):
            slug = f"{base}-{suffix}"
            suffix += 1
        return slug

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
