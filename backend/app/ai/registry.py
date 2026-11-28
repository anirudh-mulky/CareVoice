"""AI task registry: task name -> (input schema, output schema, prompt, rule fallback).

A new AI feature = a new folder in app/ai/tasks/<task>/ with schema.py, prompt.md, rules.py,
plus one line in TASKS. run_task() is the only way callers use the LLM:

1. Ask the active LLM for strict JSON (10 s timeout).
2. Invalid JSON, a timeout or a provider error -> retry once.
3. Still failing -> the rule engine answers and the result is marked needs_review.

In demo mode the active LLM is the rule engine itself, so step 1 is deterministic.
"""

import asyncio
import importlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.ai.tasks.analyse_symptom.schema import AnalyseSymptomInput, Symptom
from app.ai.tasks.extract_discharge.schema import Discharge, ExtractDischargeInput
from app.ai.tasks.extract_template.schema import ExtractTemplateInput, Template
from app.ai.tasks.score_teachback.schema import ScoreTeachbackInput, TeachBack
from app.providers.base import ProviderError
from app.providers.registry import ProviderRegistry

logger = logging.getLogger("carevoice.ai")

AI_DIR = Path(__file__).parent
INPUT_MARKER = "\n\nINPUT:\n"
LLM_TIMEOUT_SECONDS = 10.0
ATTEMPTS = 2  # first try + one retry

OutT = TypeVar("OutT", bound=BaseModel)


class Source(StrEnum):
    llm = "llm"  # a real LLM answered
    rules = "rules"  # demo mode: the rule engine is the LLM
    rules_fallback = "rules_fallback"  # the real LLM failed; rules answered


@dataclass(frozen=True)
class AITask:
    name: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    rules: Callable[[Any], BaseModel]

    @property
    def prompt(self) -> str:
        system = (AI_DIR / "system_prompt.md").read_text("utf-8").strip()
        task = (AI_DIR / "tasks" / self.name / "prompt.md").read_text("utf-8").strip()
        return f"{system}\n\n{task}"

    def build_prompt(self, data: BaseModel) -> str:
        return self.prompt + INPUT_MARKER + data.model_dump_json()


@dataclass(frozen=True)
class TaskResult(Generic[OutT]):
    output: OutT
    source: Source
    needs_review: bool = False
    error: str | None = None


def _task(name: str, input_model: type[BaseModel], output_model: type[BaseModel]) -> AITask:
    rules_module = importlib.import_module(f"app.ai.tasks.{name}.rules")
    return AITask(name, input_model, output_model, rules_module.run)


TASKS: dict[str, AITask] = {
    t.name: t
    for t in (
        _task("extract_template", ExtractTemplateInput, Template),
        _task("extract_discharge", ExtractDischargeInput, Discharge),
        _task("score_teachback", ScoreTeachbackInput, TeachBack),
        _task("analyse_symptom", AnalyseSymptomInput, Symptom),
    )
}


def get_task(name: str) -> AITask:
    try:
        return TASKS[name]
    except KeyError:
        raise KeyError(f"unknown AI task {name!r}; known: {sorted(TASKS)}") from None


def install_demo_rules(providers: ProviderRegistry) -> None:
    """Teach the demo LLM every task, so DemoLLM.json(task, prompt, schema) answers by rules."""
    for task in TASKS.values():

        def rule(prompt: str, task: AITask = task) -> dict[str, Any]:
            payload = prompt.split(INPUT_MARKER, 1)[-1]
            return task.rules(task.input_model.model_validate_json(payload)).model_dump()

        providers.demo_llm.register_rule(task.name, rule)


async def run_task(providers: ProviderRegistry, name: str, data: BaseModel) -> TaskResult[Any]:
    task = get_task(name)
    if not isinstance(data, task.input_model):
        raise TypeError(f"{name} expects {task.input_model.__name__}, got {type(data).__name__}")

    llm = providers.llm
    demo = llm is providers.demo_llm
    prompt = task.build_prompt(data)
    error: str | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            output = await asyncio.wait_for(
                llm.json(name, prompt, task.output_model), timeout=LLM_TIMEOUT_SECONDS
            )
            return TaskResult(output=output, source=Source.rules if demo else Source.llm)
        except (TimeoutError, ProviderError, ValidationError, ValueError) as exc:
            error = f"{type(exc).__name__}: {exc}"
            logger.warning("AI task %s attempt %d failed: %s", name, attempt, error)

    output = task.rules(data)
    return TaskResult(output=output, source=Source.rules_fallback, needs_review=True, error=error)
