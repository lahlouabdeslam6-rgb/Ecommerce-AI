import pytest
from fastapi import HTTPException

from app.models.ai_marketing import AIMarketingCampaign
from app.schemas.marketing import MarketingGenerateRequest
from app.services.marketing_agent import (
    OLLAMA_MARKETING_SCHEMA,
    MarketingAgentService,
)


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
