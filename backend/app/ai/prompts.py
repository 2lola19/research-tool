from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptDefinition:
    prompt_id: str
    version: str
    task: str
    template: str


class PromptRegistry:
    def __init__(self, definitions: tuple[PromptDefinition, ...]) -> None:
        keys = {(item.prompt_id, item.version) for item in definitions}
        if len(keys) != len(definitions):
            raise ValueError("Prompt registry contains duplicate ID/version pairs.")
        self._definitions = {(item.prompt_id, item.version): item for item in definitions}

    def get(self, prompt_id: str, version: str) -> PromptDefinition:
        try:
            return self._definitions[(prompt_id, version)]
        except KeyError as error:
            raise LookupError(f"Unknown prompt {prompt_id!r} version {version!r}.") from error


PROMPT_REGISTRY = PromptRegistry(())
