import pytest

from backend.app.ai.contracts import AIRequest
from backend.app.ai.mock import MockAIProvider
from backend.app.ai.models import MODEL_REGISTRY
from backend.app.ai.prompts import PromptDefinition, PromptRegistry


@pytest.mark.asyncio
async def test_mock_ai_is_deterministic_and_defers_scientific_judgment() -> None:
    provider = MockAIProvider()
    request = AIRequest(
        task="screening",
        prompt_id="screening",
        prompt_version="1",
        input_data={"title": "Example"},
        model_id="mock-default-v1",
    )

    first = await provider.generate_structured(request)
    second = await provider.generate_structured(request)

    assert first == second
    assert first.output["status"] == "NEEDS_REVIEW"
    assert first.usage == {"input_tokens": 0, "output_tokens": 0}


def test_prompt_registry_rejects_duplicate_versions() -> None:
    prompt = PromptDefinition("screening", "1", "screening", "Template")

    with pytest.raises(ValueError, match="duplicate"):
        PromptRegistry((prompt, prompt))


def test_prompt_registry_fails_closed_for_unknown_prompt() -> None:
    registry = PromptRegistry(())

    with pytest.raises(LookupError, match="Unknown prompt"):
        registry.get("missing", "1")


def test_model_registry_defaults_to_a_disabled_judgment_free_mock() -> None:
    model = MODEL_REGISTRY[0]

    assert model.internal_model_id == "mock-default-v1"
    assert model.provider == "mock"
    assert model.temperature == 0.0
    assert model.structured_output_schema == {"type": "object"}
