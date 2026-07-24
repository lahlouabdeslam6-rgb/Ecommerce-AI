import pytest
from fastapi import HTTPException

from app.services.recommendation_agent import RecommendationAgentService


def product(
    product_id: int,
    *,
    name: str,
    category: str,
    brand: str = "NUTRIFIT",
    price: float = 200,
    stock: int = 10,
    description: str = "",
    ingredients: list[dict[str, str]] | None = None,
) -> dict:
    return {
        "product_id": product_id,
        "name": name,
        "brand": brand,
        "category": category,
        "description": description,
        "price": price,
        "currency": "MAD",
        "stock": stock,
        "is_active": True,
        "images": [],
        "ingredients": ingredients or [],
        "tags": [],
        "seo_keywords": [],
    }


def test_same_category_and_shared_profile_raise_score() -> None:
    source = product(
        1,
        name="Whey Protein",
        category="Proteines",
        ingredients=[{"name": "Whey protein"}],
    )
    close = product(
        2,
        name="Whey Isolate",
        category="Proteines",
        ingredients=[{"name": "Whey protein"}],
    )
    unrelated = product(
        3,
        name="Shaker",
        category="Accessoires",
    )
    close_score = RecommendationAgentService._score_candidate(
        close,
        source_products=[source],
        objective=None,
        max_price=None,
        semantic_score=None,
    )
    unrelated_score = RecommendationAgentService._score_candidate(
        unrelated,
        source_products=[source],
        objective=None,
        max_price=None,
        semantic_score=None,
    )
    assert close_score[0] > unrelated_score[0]
    assert any("Meme categorie" in reason for reason in close_score[1])


def test_objective_and_budget_are_explained_without_medical_claims() -> None:
    candidate = product(
        2,
        name="Whey Protein Premium",
        category="Proteines",
        price=249,
        description="Proteines pour une routine sportive.",
    )
    score, reasons, _ = RecommendationAgentService._score_candidate(
        candidate,
        source_products=[],
        objective="proteines",
        max_price=300,
        semantic_score=0.6,
    )
    text = " ".join(reasons).lower()
    assert score > 0
    assert "objectif" in text
    assert "budget" in text
    assert "guerit" not in text
    assert "dosage" not in text


def test_cart_and_order_product_ids_are_deduplicated() -> None:
    assert RecommendationAgentService._unique_ints(
        [10, 20, 10, 30, 20]
    ) == [10, 20, 30]


def test_sensitive_audience_products_need_matching_context() -> None:
    prenatal = product(
        9,
        name="Prenatal DHA for pregnancy",
        category="Vitamines",
    )
    assert not RecommendationAgentService._audience_is_compatible(
        prenatal,
        context_terms={"vitamines"},
    )
    assert RecommendationAgentService._audience_is_compatible(
        prenatal,
        context_terms={"prenatal", "vitamines"},
    )


def test_explicit_protein_objective_expands_related_terms() -> None:
    terms = RecommendationAgentService._objective_terms("proteines")
    assert {"proteines", "protein", "whey", "isolate"}.issubset(terms)


def test_trace_protein_ingredient_does_not_define_product_objective() -> None:
    vitamin = product(
        14,
        name="Liquid Vitamin B Complex",
        category="Vitamines",
        description="Complexe de vitamines selon les informations fabricant.",
        ingredients=[{"name": "Soy Protein"}],
    )
    protein_terms = RecommendationAgentService._objective_terms("proteines")
    assert not (
        RecommendationAgentService._objective_product_terms(vitamin)
        & protein_terms
    )
    assert RecommendationAgentService._product_terms(vitamin) & protein_terms


def test_wrong_category_alone_does_not_define_product_objective() -> None:
    mislabeled = product(
        15,
        name="Hyaluronic Acid",
        category="protein",
        description="Joint support formula from manufacturer information.",
    )
    protein_terms = RecommendationAgentService._objective_terms("proteines")
    assert not (
        RecommendationAgentService._objective_product_terms(mislabeled)
        & protein_terms
    )


class FakeProductRepository:
    def __init__(self, source: dict | None, candidates: list[dict]) -> None:
        self.source = source
        self.candidates = candidates
        self.exclude_ids: list[int] = []

    async def get_by_product_id(self, _: int) -> dict | None:
        return self.source

    async def recommendation_candidates(
        self,
        *,
        exclude_ids: list[int],
        max_price: float | None,
        limit: int,
    ) -> list[dict]:
        self.exclude_ids = exclude_ids
        return [
            item
            for item in self.candidates
            if item["product_id"] not in exclude_ids
            and (max_price is None or item["price"] <= max_price)
        ][:limit]


@pytest.mark.asyncio
async def test_product_recommendations_work_without_qdrant() -> None:
    source = product(1, name="Creatine", category="Creatine")
    repository = FakeProductRepository(
        source,
        [
            product(1, name="Creatine", category="Creatine"),
            product(2, name="Creatine Pure", category="Creatine"),
            product(3, name="Omega 3", category="Omega 3"),
        ],
    )
    service = RecommendationAgentService(
        product_repository=repository,
    )
    result = await service.for_product(1, limit=2)
    assert repository.exclude_ids == [1]
    assert result.strategy == "catalogue"
    assert len(result.items) == 2
    assert result.items[0].product.product_id == 2
    assert "avis medical" in result.disclaimer


@pytest.mark.asyncio
async def test_inactive_source_product_is_rejected() -> None:
    source = product(1, name="Inactive", category="Autres")
    source["is_active"] = False
    service = RecommendationAgentService(
        product_repository=FakeProductRepository(source, []),
    )
    with pytest.raises(HTTPException) as error:
        await service.for_product(1, limit=4)
    assert error.value.status_code == 404
