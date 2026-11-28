"""The Part 3 gate: the eval set passes and no red-flag phrase is ever missed."""

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.ai.tasks.analyse_symptom.schema import AnalyseSymptomInput
from app.ai.tasks.common import FlagSpec, MinorSpec
from app.rules.decisions import decide
from app.rules.symptoms import analyse_symptom

EVAL_FILE = Path(__file__).parent / "fixtures" / "eval" / "symptoms.yaml"
SEED_TEMPLATES = Path(__file__).parents[1] / "app" / "seed" / "templates.json"

CASES: dict[str, list[dict[str, Any]]] = yaml.safe_load(EVAL_FILE.read_text("utf-8"))
TEMPLATES = {
    t["key"].removeprefix("template:"): t for t in json.loads(SEED_TEMPLATES.read_text("utf-8"))
}
ALL = [case | {"lang": lang} for lang, cases in CASES.items() for case in cases]


def run(case: dict[str, Any]) -> tuple[Any, Any]:
    tpl = TEMPLATES[case["template"]]
    minors = [MinorSpec.model_validate(m) for m in tpl["minor_symptoms"]]
    data = AnalyseSymptomInput(
        transcript_native=case["text"],
        language=case["lang"],
        red_flags=[FlagSpec.model_validate(f) for f in tpl["red_flags"]],
        minor_symptoms=minors,
        recovery_day=3,
    )
    symptom = analyse_symptom(data)
    return symptom, decide(symptom, minors, stt_confidence=0.9)


@pytest.mark.parametrize("lang", ["kn", "hi", "ta", "en"])
def test_each_language_has_at_least_ten_phrases(lang: str) -> None:
    assert len(CASES[lang]) >= 10


def test_set_covers_code_mixed_and_negations() -> None:
    notes = [str(c.get("note", "")) for c in ALL]
    assert sum("code-mixed" in n for n in notes) >= 4
    assert sum("negation" in n for n in notes) >= 8


@pytest.mark.parametrize("case", ALL, ids=[c["id"] for c in ALL])
def test_eval_case(case: dict[str, Any]) -> None:
    symptom, decision = run(case)
    assert sorted(symptom.matched_flag_ids) == sorted(case.get("flags", [])), symptom
    if decision.type == "minor" or case["type"] == "minor":
        assert sorted(symptom.matched_minor_ids) == sorted(case.get("minors", [])), symptom
    assert decision.type == case["type"], (decision, symptom)


def test_no_red_flag_in_the_set_is_missed() -> None:
    expected = missed = 0
    misses = []
    for case in ALL:
        symptom, decision = run(case)
        for flag in case.get("flags", []):
            expected += 1
            if flag not in symptom.matched_flag_ids or decision.type != "alert":
                missed += 1
                misses.append((case["id"], flag))
    assert expected >= 30
    assert missed == 0, f"missed red flags: {misses}"
