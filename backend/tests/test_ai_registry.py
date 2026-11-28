import asyncio
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from app.ai.registry import TASKS, Source, install_demo_rules, run_task
from app.ai.tasks.common import TemplateRef
from app.ai.tasks.extract_discharge.schema import Discharge, ExtractDischargeInput
from app.providers.base import ProviderError, ProviderKind
from app.providers.registry import ProviderRegistry
from tests.support import make_settings

pytestmark = pytest.mark.anyio

AI_DIR = Path(__file__).parents[1] / "app" / "ai"
DATA = ExtractDischargeInput(
    transcript="Ramesh, 68, cataract right eye, language Kannada",
    templates=[TemplateRef(name="Cataract surgery", condition="cataract")],
)


def registry(tmp_path: Path) -> ProviderRegistry:
    providers = ProviderRegistry(make_settings(tmp_path))
    install_demo_rules(providers)
    return providers


def test_four_tasks_each_with_schema_prompt_and_rules() -> None:
    assert sorted(TASKS) == [
        "analyse_symptom",
        "extract_discharge",
        "extract_template",
        "score_teachback",
    ]
    for name, task in TASKS.items():
        folder = AI_DIR / "tasks" / name
        assert {"schema.py", "prompt.md", "rules.py"} <= {p.name for p in folder.iterdir()}
        assert "Never diagnose" in task.prompt  # shared system prompt is included


async def test_demo_mode_answers_through_the_rule_engine(tmp_path: Path) -> None:
    result = await run_task(registry(tmp_path), "extract_discharge", DATA)
    assert result.source is Source.rules
    assert not result.needs_review
    assert isinstance(result.output, Discharge)
    assert result.output.patient_name == "Ramesh"


class FakeLLM:
    name = "fake"

    def __init__(self, replies: list[Any]) -> None:
        self.replies = replies
        self.calls = 0

    async def json(self, task: str, prompt: str, schema: type[BaseModel]) -> BaseModel:
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if reply == "slow":
            await asyncio.sleep(1)
        return schema.model_validate(reply)


def with_llm(tmp_path: Path, llm: FakeLLM) -> ProviderRegistry:
    providers = registry(tmp_path)
    providers._active[ProviderKind.llm] = llm
    return providers


async def test_real_llm_answer_is_used(tmp_path: Path) -> None:
    llm = FakeLLM([{"patient_name": "Ramesh", "age": 68}])
    result = await run_task(with_llm(tmp_path, llm), "extract_discharge", DATA)
    assert result.source is Source.llm and llm.calls == 1


async def test_invalid_json_retries_once_then_succeeds(tmp_path: Path) -> None:
    llm = FakeLLM([{"age": "sixty-eight"}, {"patient_name": "Ramesh", "age": 68}])
    result = await run_task(with_llm(tmp_path, llm), "extract_discharge", DATA)
    assert result.source is Source.llm and llm.calls == 2


async def test_two_failures_fall_back_to_rules_and_need_review(tmp_path: Path) -> None:
    llm = FakeLLM([ProviderError("down"), {"age": 500}])
    result = await run_task(with_llm(tmp_path, llm), "extract_discharge", DATA)
    assert llm.calls == 2
    assert result.source is Source.rules_fallback
    assert result.needs_review
    assert result.output.patient_name == "Ramesh"  # the rule engine still did the job


async def test_timeout_counts_as_a_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.ai.registry.LLM_TIMEOUT_SECONDS", 0.01)
    llm = FakeLLM(["slow", "slow"])
    result = await run_task(with_llm(tmp_path, llm), "extract_discharge", DATA)
    assert result.source is Source.rules_fallback
    assert "TimeoutError" in (result.error or "")


async def test_wrong_input_type_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        await run_task(registry(tmp_path), "analyse_symptom", DATA)


async def test_unknown_task_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        await run_task(registry(tmp_path), "diagnose", DATA)
