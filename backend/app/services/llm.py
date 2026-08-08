"""Thin wrapper around the Anthropic API.

Model names, max tokens, and retry count come from env. Daily calls (morning
parse and prioritize, evening reflection) use the daily model; the Sunday
retro uses the larger retro model. The wrapper returns plain text; callers
own prompts, parsing, and length caps. Tests replace it via the get_llm
dependency, so no real API call ever happens in the suite.
"""

from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Annotated, Protocol

from anthropic import Anthropic, AnthropicError
from fastapi import Depends

from app.core.config import settings

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class LlmUnavailable(Exception):
    """The agent cannot think right now: no key, or the API refused."""


class LlmClient(Protocol):
    def complete_daily(self, prompt: str) -> str: ...

    def complete_retro(self, prompt: str) -> str: ...


class AnthropicClient:
    """Built lazily, like the calendar client.

    An unset key must not blow up at import time, and it must not surface as
    a 500 with a stack trace either: planning is the first thing the owner
    touches, so the reason has to reach the screen.
    """

    def __init__(self) -> None:
        self._client: Anthropic | None = None

    def _get_client(self) -> Anthropic:
        if self._client is None:
            if not settings.anthropic_api_key:
                raise LlmUnavailable("ANTHROPIC_API_KEY is not set")
            self._client = Anthropic(
                api_key=settings.anthropic_api_key,
                max_retries=settings.anthropic_max_retries,
            )
        return self._client

    def _complete(self, model: str, prompt: str) -> str:
        client = self._get_client()
        try:
            response = client.messages.create(
                model=model,
                max_tokens=settings.anthropic_max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except AnthropicError as error:
            raise LlmUnavailable(str(error)) from error
        return "".join(block.text for block in response.content if block.type == "text")

    def complete_daily(self, prompt: str) -> str:
        return self._complete(settings.anthropic_model_daily, prompt)

    def complete_retro(self, prompt: str) -> str:
        return self._complete(settings.anthropic_model_retro, prompt)


@lru_cache(maxsize=1)
def get_llm() -> LlmClient:
    return AnthropicClient()


LlmDep = Annotated[LlmClient, Depends(get_llm)]


@lru_cache(maxsize=8)
def load_prompt(name: str) -> Template:
    """Load a versioned prompt file as a string.Template.

    Templates use $placeholders (not str.format) so literal JSON braces in
    prompt text never collide with substitution.
    """
    return Template((PROMPTS_DIR / name).read_text(encoding="utf-8"))
