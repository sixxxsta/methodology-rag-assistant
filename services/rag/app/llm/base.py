from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        message: str,
        *,
        context: str = "",
        language: str | None = None,
    ) -> str:
        raise NotImplementedError
