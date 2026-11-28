"""Provider failover and demo fault injection.

- FailoverTranslator: primary -> demo phrasebook -> the original text. Translation never
  crashes a request; when unsure the English (or original) wording is kept.
- SIMULATE_FAILURES (comma list, e.g. "llm,translate"): makes the named provider fail on
  every call, so the error-handling paths can be shown on demand. Empty in production.
"""

import logging
from typing import TypeVar

from pydantic import BaseModel

from app.providers.base import ProviderError, Translator

logger = logging.getLogger("carevoice.providers")
SchemaT = TypeVar("SchemaT", bound=BaseModel)
SIMULATABLE = frozenset({"llm", "translate"})


class FailingLLM:
    """Always fails, like a real LLM that is down or returning broken JSON."""

    name = "simulated-failure"

    async def json(self, task: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        raise ProviderError("Simulated LLM failure")


class FailingTranslator:
    name = "simulated-failure"

    async def translate(self, text: str, src: str, dst: str) -> str:
        raise ProviderError("Simulated translator failure")


class FailoverTranslator:
    """Try the primary, then the demo phrasebook, then keep the text as it is."""

    def __init__(self, primary: Translator, fallback: Translator) -> None:
        self.primary = primary
        self.fallback = fallback
        self.name = getattr(primary, "name", "translator")

    async def translate(self, text: str, src: str, dst: str) -> str:
        for provider in (self.primary, self.fallback):
            try:
                return await provider.translate(text, src, dst)
            except Exception as exc:  # noqa: BLE001 - fall through to the next one
                logger.warning("translator %s failed: %s", getattr(provider, "name", "?"), exc)
            if provider is self.fallback:
                break
        return text


def simulated(raw: str) -> frozenset[str]:
    names = {n.strip().lower() for n in raw.split(",") if n.strip()}
    unknown = names - SIMULATABLE
    if unknown:
        logger.warning("SIMULATE_FAILURES: ignoring unknown names %s", sorted(unknown))
    return frozenset(names & SIMULATABLE)
