from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.models.ai_marketing import AIMarketingCampaign
from app.schemas.marketing import MarketingGenerateRequest
from app.schemas.marketing import PromotionProductScore
from app.schemas.product import ProductResponse
from app.services.marketing_agent import (
    OLLAMA_MARKETING_SCHEMA,
    MarketingAgentService,
)
from app.services.promotion_scoring import PromotionScoringService


def marketing_request(
    channels: list[str] | None = None,
) -> MarketingGenerateRequest:
    return MarketingGenerateRequest(
        campaign_type="promotion",
        topic="Routine creatine NUTRIFIT",
        objective="Presenter la selection sans promesse medicale",
        audience="sportifs au Maroc",
        tone="premium",
        channels=channels or ["instagram", "email", "whatsapp"],
    )


def test_marketing_agent_normalizes_selected_channels() -> None:
    generated = MarketingAgentService._normalize_generated(
        """
        {
          "campaign_title": "Routine creatine NUTRIFIT",
          "headline": "<strong>Construisez votre routine</strong>",
          "core_message": "<p>Explorez les produits NUTRIFIT et consultez chaque fiche avant de faire votre choix.</p>",
          "email_subject": "Votre routine NUTRIFIT",
          "email_body": "Decouvrez notre selection et choisissez selon vos objectifs.",
          "whatsapp_message": "La selection creatine NUTRIFIT est disponible.",
          "social_caption": "Une routine claire commence par une information transparente.",
          "cta_label": "Voir les produits",
          "hashtags": ["NUTRIFIT", "#Creatine", "Nutrition Sportive"],
          "recommended_schedule": "Mardi a 18h, puis rappel vendredi."
        }
        """,
        marketing_request(),
    )
    assert generated.headline == "Construisez votre routine"
    assert "<" not in generated.core_message
    assert generated.email_subject == "Votre routine NUTRIFIT"
    assert generated.whatsapp_message is not None
    assert generated.social_caption is not None
    assert generated.hashtags == [
        "#NUTRIFIT",
        "#Creatine",
        "#NutritionSportive",
    ]


def test_marketing_agent_removes_unselected_channel_content() -> None:
    generated = MarketingAgentService._normalize_generated(
        """
        {
          "campaign_title": "Campagne Instagram NUTRIFIT",
          "headline": "Nutrition et performance au quotidien",
          "core_message": "Decouvrez des informations claires pour choisir les produits adaptes a vos objectifs sportifs.",
          "email_subject": "Email non demande",
          "email_body": "Ce contenu ne doit pas etre conserve.",
          "whatsapp_message": "Message non demande",
          "social_caption": "Explorez la selection NUTRIFIT et consultez les fiches produits.",
          "cta_label": "Voir les produits",
          "hashtags": ["NUTRIFIT"],
          "recommended_schedule": "Mercredi a 19h."
        }
        """,
        marketing_request(["instagram"]),
    )
    assert generated.email_subject is None
    assert generated.email_body is None
    assert generated.whatsapp_message is None
    assert generated.social_caption is not None


def test_marketing_agent_rejects_invalid_json() -> None:
    with pytest.raises(HTTPException) as error:
        MarketingAgentService._normalize_generated(
            "not-json",
            marketing_request(),
        )
    assert error.value.status_code == 502


def test_marketing_ollama_schema_has_no_nullable_grammar() -> None:
    assert "anyOf" not in str(OLLAMA_MARKETING_SCHEMA)
    assert len(OLLAMA_MARKETING_SCHEMA["required"]) == 10


def test_marketing_approval_requires_selected_channel_content() -> None:
    campaign = AIMarketingCampaign(
        channels_json='["email", "whatsapp"]',
        email_subject=None,
        email_body=None,
        whatsapp_message="Message WhatsApp disponible",
    )
    with pytest.raises(HTTPException) as error:
        MarketingAgentService._validate_channels(campaign)
    assert error.value.status_code == 409
    assert "email" in str(error.value.detail)


def test_manual_pack_requires_at_least_two_products() -> None:
    with pytest.raises(ValueError):
        MarketingGenerateRequest(
            campaign_type="promotion",
            topic="Pack performance",
            objective="Proposer une offre controlee",
            channels=["instagram"],
            promotion_kind="pack",
            selection_mode="manual",
            product_ids=[10],
        )


def test_manual_pack_accepts_more_than_four_products() -> None:
    request = MarketingGenerateRequest(
        campaign_type="promotion",
        topic="Pack performance complet",
        objective="Proposer une offre controlee",
        channels=["instagram"],
        promotion_kind="pack",
        selection_mode="manual",
        product_ids=[10, 20, 30, 40, 50, 60],
    )

    assert request.product_ids == [10, 20, 30, 40, 50, 60]


def test_promotion_score_uses_sales_stock_and_momentum() -> None:
    products = [
        ProductResponse(
            product_id=1,
            name="Whey",
            category="protein",
            price=300,
            stock=40,
        ),
        ProductResponse(
            product_id=2,
            name="Creatine",
            category="creatine",
            price=200,
            stock=20,
        ),
    ]
    scored = PromotionScoringService._score_products(
        products,
        sales_90=[
            {"product_id": 1, "quantity": 30},
            {"product_id": 2, "quantity": 5},
        ],
        sales_30=[
            {"product_id": 1, "quantity": 15},
            {"product_id": 2, "quantity": 1},
        ],
        previous_30=[
            {"product_id": 1, "quantity": 8},
            {"product_id": 2, "quantity": 2},
        ],
    )
    assert scored[0].product_id == 1
    assert scored[0].score > scored[1].score
    assert "demande recente en hausse" in scored[0].reasons


def test_pack_selection_prefers_co_purchase_and_category_diversity() -> None:
    scored = [
        PromotionProductScore(
            product_id=1,
            name="Whey",
            category="protein",
            price=300,
            stock=30,
            score=90,
        ),
        PromotionProductScore(
            product_id=2,
            name="Creatine",
            category="creatine",
            price=200,
            stock=30,
            score=70,
        ),
        PromotionProductScore(
            product_id=3,
            name="Autre whey",
            category="protein",
            price=280,
            stock=30,
            score=80,
        ),
    ]
    selected = PromotionScoringService._select_pack(
        scored,
        [
            {
                "left_product_id": 1,
                "right_product_id": 2,
                "order_count": 12,
            }
        ],
    )
    assert selected[0].product_id == 1
    assert selected[1].product_id == 2
    assert any("achete avec" in reason for reason in selected[1].reasons)


@pytest.mark.asyncio
async def test_automatic_pack_suggestion_selects_only_three_products() -> None:
    products = [
        ProductResponse(
            product_id=product_id,
            name=f"Produit {product_id}",
            category=f"Categorie {product_id % 4}",
            price=100 + product_id,
            stock=40 - product_id,
        )
        for product_id in range(1, 11)
    ]
    service = PromotionScoringService(AsyncMock())
    service.products.list_products = AsyncMock(
        return_value=SimpleNamespace(items=products)
    )
    service.analytics.top_products = AsyncMock(return_value=[])
    service.analytics.co_purchase_pairs = AsyncMock(return_value=[])
    service.signals.cost_map = AsyncMock(return_value={})
    service.signals.view_counts = AsyncMock(return_value={})

    suggestion = await service.suggest(
        promotion_kind="pack",
        product_ids=[],
    )

    assert len(suggestion.products) == 3
    assert len(suggestion.products) < len(products)


@pytest.mark.asyncio
async def test_suggested_discount_preserves_minimum_margin() -> None:
    product = ProductResponse(
        product_id=1,
        name="Produit marge controlee",
        category="wellness",
        price=100,
        stock=30,
    )
    service = PromotionScoringService(AsyncMock())
    service.products.list_products = AsyncMock(
        return_value=SimpleNamespace(items=[product])
    )
    service.analytics.top_products = AsyncMock(return_value=[])
    service.analytics.co_purchase_pairs = AsyncMock(return_value=[])
    service.signals.cost_map = AsyncMock(return_value={1: 80})
    service.signals.view_counts = AsyncMock(return_value={})

    suggestion = await service.suggest(
        promotion_kind="single_product",
        product_ids=[],
    )

    assert suggestion.suggested_discount_percentage == 5.9
    assert any(
        "Marge brute minimale de 15%" in note
        for note in suggestion.data_notes
    )


def test_promotion_score_uses_conversion_and_private_margin() -> None:
    product = ProductResponse(
        product_id=7,
        name="Omega 3",
        category="wellness",
        price=200,
        stock=30,
    )
    scored = PromotionScoringService._score_products(
        [product],
        sales_90=[{"product_id": 7, "quantity": 10}],
        sales_30=[{"product_id": 7, "quantity": 4}],
        previous_30=[{"product_id": 7, "quantity": 3}],
        views_90={7: 50},
        costs={7: 100},
    )
    assert "conversion observee: 20.0%" in scored[0].reasons
    assert "marge brute renseignee: 50.0%" in scored[0].reasons
