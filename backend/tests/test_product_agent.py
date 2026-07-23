import pytest
from fastapi import HTTPException

from app.services.product_agent import ProductAgentService
from app.schemas.product import ProductResponse


VALID_SUGGESTION = """
{
  "description": "Une formule de nutrition sportive presentee de maniere claire, factuelle et adaptee aux objectifs quotidiens des sportifs.",
  "category": "Vitamines et mineraux",
  "seo_title": "Complexe vitamines NUTRIFIT pour sportifs",
  "seo_description": "Decouvrez un complexe de vitamines pour completer une routine de nutrition sportive avec des informations produit claires.",
  "seo_keywords": ["vitamines sport", "nutrition sportive", "routine active"],
  "tags": ["vitamines", "sport", "bien-etre"]
}
"""


def test_product_agent_parses_and_cleans_json() -> None:
    suggestion = ProductAgentService._parse_suggestion(VALID_SUGGESTION)
    assert suggestion.category == "Vitamines et mineraux"
    assert suggestion.seo_keywords == [
        "vitamines sport",
        "nutrition sportive",
        "routine active",
    ]


def test_product_agent_accepts_json_code_fence() -> None:
    suggestion = ProductAgentService._parse_suggestion(
        f"```json\n{VALID_SUGGESTION}\n```"
    )
    assert suggestion.tags == ["vitamines", "sport", "bien-etre"]


def test_product_agent_rejects_invalid_response() -> None:
    with pytest.raises(HTTPException) as error:
        ProductAgentService._parse_suggestion('{"description": "trop court"}')
    assert error.value.status_code == 502


def test_product_agent_deduplicates_terms() -> None:
    assert ProductAgentService._clean_terms(
        [" Protein ", "protein", "SPORT", "", "sport"]
    ) == ["protein", "sport"]


def test_product_agent_normalizes_incomplete_but_valid_json() -> None:
    product = ProductResponse(
        product_id=23445,
        name="Quick Mass Loaded Vanilla",
        brand="ALLMAX NUTRITION",
        category="protein",
        description="Informations fabricant.",
        currency="MAD",
        stock=10,
    )
    suggestion = ProductAgentService._normalize_suggestion(
        """
        {
          "description": "Mass gainer en poudre.",
          "category": "Protein",
          "seo_title": "",
          "seo_description": "",
          "seo_keywords": ["gainer"],
          "tags": []
        }
        """,
        product,
    )
    assert suggestion.category == "Proteines"
    assert len(suggestion.description) >= 40
    assert len(suggestion.seo_title) >= 10
    assert len(suggestion.seo_description) >= 40
    assert len(suggestion.seo_keywords) >= 3
    assert len(suggestion.tags) >= 2
