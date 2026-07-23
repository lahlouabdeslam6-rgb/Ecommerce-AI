import pytest
from fastapi import HTTPException

from app.schemas.content import ContentGenerateRequest
from app.services.content_agent import (
    OLLAMA_CONTENT_SCHEMA,
    ContentAgentService,
)
from app.services.support import SupportService


def test_content_agent_normalizes_generated_content() -> None:
    request = ContentGenerateRequest(
        content_type="promotion",
        topic="Routine creatine NUTRIFIT",
        audience="sportifs au Maroc",
        tone="premium",
    )
    generated = ContentAgentService._normalize_generated(
        """
        {
          "title": "Routine creatine NUTRIFIT",
          "subtitle": "La regularite au coeur de votre programme",
          "body": "Decouvrez une selection NUTRIFIT consacree a la creatine et consultez chaque fiche produit avant votre choix.",
          "cta_label": "Voir la selection",
          "hashtags": ["NUTRIFIT", "#Creatine", "Nutrition Sportive"]
        }
        """,
        request,
    )
    assert generated.cta_label == "Voir les produits"
    assert generated.hashtags == [
        "#NUTRIFIT",
        "#Creatine",
        "#NutritionSportive",
    ]


def test_content_agent_completes_short_fields() -> None:
    request = ContentGenerateRequest(
        content_type="faq",
        topic="Bien lire une etiquette",
    )
    generated = ContentAgentService._normalize_generated(
        '{"title":"FAQ","body":"Court","hashtags":[]}',
        request,
    )
    assert len(generated.title) >= 5
    assert len(generated.body) >= 30


def test_content_agent_rejects_non_json() -> None:
    request = ContentGenerateRequest(
        content_type="social_post",
        topic="Nouveautes NUTRIFIT",
    )
    with pytest.raises(HTTPException) as error:
        ContentAgentService._normalize_generated("not-json", request)
    assert error.value.status_code == 502


def test_ollama_content_schema_has_no_nullable_grammar() -> None:
    assert "anyOf" not in str(OLLAMA_CONTENT_SCHEMA)
    assert set(OLLAMA_CONTENT_SCHEMA["required"]) == {
        "title",
        "subtitle",
        "body",
        "cta_label",
        "hashtags",
    }


def test_content_agent_strips_markup_and_uses_catalogue_cta() -> None:
    request = ContentGenerateRequest(
        content_type="promotion",
        topic="Promotion creatine",
    )
    generated = ContentAgentService._normalize_generated(
        """
        {
          "title": "<strong>Selection creatine</strong>",
          "subtitle": "",
          "body": "<p>Decouvrez les produits.</p><ul><li>Creatine premium</li><li>Informations transparentes</li></ul>",
          "cta_label": "Contactez-nous",
          "hashtags": ["Creatine"]
        }
        """,
        request,
    )
    assert "<" not in generated.title
    assert "<" not in generated.body
    assert "- Creatine premium" in generated.body
    assert generated.cta_label == "Voir les produits"


def test_staff_ticket_notifications_use_role_workspace() -> None:
    assert SupportService._staff_ticket_link("admin", 42) == (
        "/admin?tab=messages&ticket=42"
    )
    assert SupportService._staff_ticket_link("support", 42) == (
        "/support?ticket=42"
    )
