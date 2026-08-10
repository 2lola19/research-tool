from typing import Any, Protocol


class ResearchEngine(Protocol):
    name: str
    version: str

    async def execute(self, command: dict[str, Any]) -> dict[str, Any]: ...
