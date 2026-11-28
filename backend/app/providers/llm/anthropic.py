"""Claude via the official Anthropic SDK.

Each AI task asks for strict JSON matching its Pydantic schema; the SDK's structured
outputs (`messages.parse` with `output_format`) guarantee the shape. Low effort keeps the
patient's read-back fast; the rule engine still answers if Claude fails or times out.
Server-side fallbacks ("default") re-run a policy refusal on a fallback model inside the
same call; a refusal that remains raises ProviderError, so the rules take over.
"""

import logging
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from app.core.config import Settings
from app.providers.base import ProviderError

logger = logging.getLogger("carevoice.providers.anthropic")
SchemaT = TypeVar("SchemaT", bound=BaseModel)
DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 4096  # the task outputs are small JSON objects


class AnthropicLLM:
    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        settings: Settings,
        client: anthropic.AsyncAnthropic | None = None,
    ) -> None:
        self.model = settings.llm_model or DEFAULT_MODEL
        # One retry inside the SDK; run_task adds its own retry and the rules fallback.
        self.client = client or anthropic.AsyncAnthropic(
            api_key=api_key, max_retries=1, timeout=settings.provider_timeout_seconds
        )

    async def json(self, task: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        try:
            response = await self.client.beta.messages.parse(
                model=self.model,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
                output_format=schema,
                output_config={"effort": "low"},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.APIStatusError as exc:
            logger.warning("Claude %s failed: HTTP %s", task, exc.status_code)
            raise ProviderError(f"Claude HTTP {exc.status_code}") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("Claude connection error") from exc
        if response.stop_reason == "refusal":
            raise ProviderError("Claude declined the request")
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            raise ProviderError(f"Claude gave no usable JSON (stop: {response.stop_reason})")
        parsed: SchemaT = response.parsed_output
        return parsed
