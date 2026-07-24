from app.schemas.safety import SafetyAIResult
from app.services.safety_agent import (
    OLLAMA_SAFETY_SCHEMA,
    SafetyAgentService,
)


def test_safe_commercial_copy_passes_rule_review() -> None:
    result = SafetyAgentService._rule_review(
        "Decouvrez la selection NUTRIFIT et consultez la fiche produit "
        "avant de choisir selon vos objectifs."
    )
    assert result["status"] == "safe"
    assert result["risk_level"] == "low"
    assert result["matched_rules"] == []


def test_medical_cure_claim_is_blocked() -> None:
    result = SafetyAgentService._rule_review(
        "Ce complement guerit le diabete rapidement."
    )
    assert result["status"] == "blocked"
    assert result["risk_level"] == "high"
    assert "medical_cure" in result["matched_rules"]
    assert "sensitive_health_context" in result["matched_rules"]


def test_benign_use_of_traite_is_not_a_medical_claim() -> None:
    result = SafetyAgentService._rule_review(
        "Notre equipe traite votre commande dans les meilleurs delais."
    )
    assert result["status"] == "safe"
    assert "medical_cure" not in result["matched_rules"]


def test_medicine_replacement_is_blocked() -> None:
    result = SafetyAgentService._rule_review(
        "Arrete ton traitement et remplace ton medicament par ce produit."
    )
    assert result["status"] == "blocked"
    assert "medicine_replacement" in result["matched_rules"]


def test_dosage_requires_human_review() -> None:
    result = SafetyAgentService._rule_review(
        "La fiche indique une portion de 5 g par jour."
    )
    assert result["status"] == "warning"
    assert result["risk_level"] == "medium"
    assert "dosage_mentioned" in result["matched_rules"]


def test_low_confidence_semantic_block_is_downgraded_to_warning() -> None:
    merged = SafetyAgentService._merge_results(
        {
            "status": "safe",
            "risk_level": "low",
            "reasons": [],
            "recommendations": [],
            "matched_rules": [],
        },
        SafetyAIResult(
            status="blocked",
            risk_level="high",
            reasons=["Affirmation ambigue."],
            recommendations=["Verifier avec une personne."],
            confidence=0.6,
        ),
        ai_unavailable=False,
    )
    assert merged["status"] == "warning"
    assert merged["risk_level"] == "medium"


def test_ai_outage_requires_human_review() -> None:
    merged = SafetyAgentService._merge_results(
        {
            "status": "safe",
            "risk_level": "low",
            "reasons": [],
            "recommendations": [],
            "matched_rules": [],
        },
        None,
        ai_unavailable=True,
    )
    assert merged["status"] == "warning"
    assert "indisponible" in merged["reasons"][0]


def test_safety_ollama_schema_has_no_nullable_grammar() -> None:
    assert "anyOf" not in str(OLLAMA_SAFETY_SCHEMA)
    assert set(OLLAMA_SAFETY_SCHEMA["required"]) == {
        "status",
        "risk_level",
        "reasons",
        "recommendations",
        "confidence",
    }
