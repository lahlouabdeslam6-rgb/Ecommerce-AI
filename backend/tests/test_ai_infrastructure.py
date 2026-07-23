from app.services.ai_infrastructure import AIInfrastructureService


def test_ollama_model_matching_accepts_explicit_tag() -> None:
    assert AIInfrastructureService._model_is_installed(
        "qwen2.5:3b",
        ["qwen2.5:3b"],
    )


def test_ollama_model_matching_accepts_latest_tag() -> None:
    assert AIInfrastructureService._model_is_installed(
        "nomic-embed-text",
        ["nomic-embed-text:latest"],
    )


def test_ollama_model_matching_rejects_missing_model() -> None:
    assert not AIInfrastructureService._model_is_installed(
        "nomic-embed-text",
        ["qwen2.5:3b"],
    )
