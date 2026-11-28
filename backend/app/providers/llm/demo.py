"""Demo LLM: a rule-based stand-in that returns the same strict JSON a real LLM would.

Each AI task registers a rule function (Part 3 adds them under app/ai/tasks/<task>/rules.py).
The result is validated against the task's Pydantic schema exactly like real LLM output,
so callers cannot tell the difference except by quality.
"""

from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from app.providers.base import ProviderError, SchemaT

Rule = Callable[[str], dict[str, Any]]


class DemoLLM:
    name = "demo"

    def __init__(self) -> None:
        self._rules: dict[str, Rule] = {}

    def register_rule(self, task: str, rule: Rule) -> None:
        self._rules[task] = rule

    def has_rule(self, task: str) -> bool:
        return task in self._rules

    async def json(self, task: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        rule = self._rules.get(task)
        if rule is None:
            raise ProviderError(f"no demo rule registered for task {task!r}")
        try:
            return schema.model_validate(rule(prompt))
        except ValidationError as exc:
            raise ProviderError(f"demo rule for {task!r} returned invalid data: {exc}") from exc
