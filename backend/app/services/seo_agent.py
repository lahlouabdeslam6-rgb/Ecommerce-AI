from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.operations import OperationsRepository
from app.repositories.product import ProductRepository
from app.schemas.seo import (
    SEOApplyResponse,
    SEOAuditItem,
    SEOAuditReport,
    SEOAuditSummary,
    SEOFaqItem,
    SEOProposal,
)
from app.services.safety_agent import SafetyAgentService


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug[:170].rstrip("-") or "produit"


class SEOAgentService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        product_repository: ProductRepository | None = None,
        operations: OperationsRepository | None = None,
    ) -> None:
        self.session = session
        self.product_repository = product_repository or ProductRepository()
        self.operations = operations or OperationsRepository(session)

    async def audit(self) -> SEOAuditReport:
        products, _ = await self.product_repository.list_products(
            skip=0,
            limit=1000,
            sort_by="newest",
            active_only=True,
        )
        items = [self._audit_product(product) for product in products]
        items.sort(key=lambda item: (item.score, item.name.lower()))
        scores = [item.score for item in items]
        summary = SEOAuditSummary(
            products=len(items),
            excellent=sum(item.score >= 80 for item in items),
            needs_work=sum(50 <= item.score < 80 for item in items),
            critical=sum(item.score < 50 for item in items),
            average_score=round(sum(scores) / len(scores), 1) if scores else 0,
        )
        return SEOAuditReport(
            generated_at=datetime.now(UTC),
            summary=summary,
            items=items,
        )

    async def preview(self, product_id: int) -> SEOProposal:
        product = await self.product_repository.get_by_product_id(product_id)
        if product is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit introuvable")

        name = str(product.get("name") or "Produit NUTRIFIT").strip()
        brand = str(product.get("brand") or "NUTRIFIT").strip()
        category = str(product.get("category") or "nutrition sportive").strip()
        slug = str(product.get("slug") or "").strip() or (
            f"{_slugify(name)}-{product_id}"
        )
        title = str(product.get("seo_title") or "").strip()
        if len(title) < 10:
            title = f"{name} | {brand}"
        if len(title) < 10:
            title = f"{name} - Complément NUTRIFIT"
        title = title[:70].rstrip(" |-")

        description = str(product.get("seo_description") or "").strip()
        if len(description) < 40:
            product_description = re.sub(
                r"\s+",
                " ",
                str(product.get("description") or ""),
            ).strip()
            description = (
                product_description[:175]
                if len(product_description) >= 70
                else (
                    f"Découvrez {name} de {brand}, sélectionné dans notre "
                    f"catalogue {category} NUTRIFIT au Maroc."
                )
            )
        description = description[:180].rstrip(" ,;") + (
            "." if not description.rstrip().endswith((".", "!", "?")) else ""
        )
        description = description[:180]

        ingredients = [
            str(item.get("name") or "").strip()
            for item in product.get("ingredients") or []
            if isinstance(item, dict) and item.get("name")
        ]
        candidates = [
            *(product.get("seo_keywords") or []),
            name,
            brand,
            category,
            *ingredients[:3],
            "nutrition sportive Maroc",
        ]
        keywords: list[str] = []
        for value in candidates:
            cleaned = re.sub(r"\s+", " ", str(value)).strip()[:80]
            if cleaned and cleaned.lower() not in {
                keyword.lower() for keyword in keywords
            }:
                keywords.append(cleaned)
        while len(keywords) < 3:
            keywords.append(
                ["compléments alimentaires", "performance sportive", "NUTRIFIT"][
                    len(keywords)
                ]
            )

        image_alt = str(product.get("image_alt") or "").strip() or (
            f"{name} {brand} - complément de {category}"
        )
        faq = [
            SEOFaqItem(
                question=f"Qu'est-ce que {name} ?",
                answer=(
                    f"{name} est un produit de la marque {brand}, classé dans "
                    f"la catégorie {category}. Consultez la fiche pour sa "
                    "composition complète."
                ),
            ),
            SEOFaqItem(
                question=f"{name} est-il disponible ?",
                answer=(
                    "La disponibilité affichée sur la fiche produit correspond "
                    "au stock actuellement enregistré sur NUTRIFIT."
                ),
            ),
        ]
        return SEOProposal(
            product_id=product_id,
            slug=slug,
            seo_title=title,
            seo_description=description,
            seo_keywords=keywords[:8],
            image_alt=image_alt[:180],
            seo_faq=faq,
        )

    async def apply(
        self,
        product_id: int,
        proposal: SEOProposal,
        actor: User,
    ) -> SEOApplyResponse:
        if proposal.product_id != product_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "L'identifiant du produit ne correspond pas",
            )
        current = await self.product_repository.get_by_product_id(product_id)
        if current is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit introuvable")
        safety_text = "\n".join(
            [
                proposal.seo_title,
                proposal.seo_description,
                proposal.image_alt,
                *[item.answer for item in proposal.seo_faq],
            ]
        )
        await SafetyAgentService(self.session).enforce(
            safety_text,
            source_type="seo_proposal",
            source_id=product_id,
            action="seo.apply",
            actor_id=actor.id,
            actor_role=actor.role,
        )
        before = self._audit_product(current).score
        fields: dict[str, Any] = proposal.model_dump(
            include={
                "slug",
                "seo_title",
                "seo_description",
                "seo_keywords",
                "image_alt",
                "seo_faq",
            },
            mode="json",
        )
        updated = await self.product_repository.update_product(
            product_id,
            fields,
        )
        if updated is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit introuvable")
        after = self._audit_product(updated).score
        self.operations.add_audit(
            actor_id=actor.id,
            actor_role=actor.role,
            action="ai.seo.apply",
            entity_type="product",
            entity_id=product_id,
            details={"score_before": before, "score_after": after},
        )
        await self.session.commit()
        return SEOApplyResponse(
            product_id=product_id,
            applied_fields=list(fields),
            score_before=before,
            score_after=after,
        )

    @staticmethod
    def _audit_product(product: dict[str, Any]) -> SEOAuditItem:
        score = 0
        issues: list[str] = []
        title = str(product.get("seo_title") or "").strip()
        meta = str(product.get("seo_description") or "").strip()
        keywords = product.get("seo_keywords") or []
        description = str(product.get("description") or "").strip()

        if 10 <= len(title) <= 70:
            score += 20
        else:
            issues.append("Titre SEO absent ou longueur incorrecte")
        if 70 <= len(meta) <= 180:
            score += 20
        else:
            issues.append("Méta description absente ou trop courte")
        if 3 <= len(keywords) <= 12:
            score += 15
        else:
            issues.append("Moins de 3 mots-clés SEO")
        if len(description) >= 100:
            score += 15
        else:
            issues.append("Description produit trop courte")
        if product.get("category"):
            score += 10
        else:
            issues.append("Catégorie absente")
        if product.get("images"):
            score += 10
        else:
            issues.append("Aucune image produit")
        if product.get("image_alt"):
            score += 5
        else:
            issues.append("Texte alternatif d'image absent")
        if product.get("slug"):
            score += 5
        else:
            issues.append("Slug SEO absent")

        return SEOAuditItem(
            product_id=int(product["product_id"]),
            name=str(product.get("name") or "Produit"),
            brand=product.get("brand"),
            score=score,
            issues=issues,
            slug=product.get("slug"),
        )
