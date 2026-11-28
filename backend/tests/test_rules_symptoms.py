import json
from pathlib import Path

import pytest

from app.ai.tasks.analyse_symptom.schema import AnalyseSymptomInput, Symptom
from app.ai.tasks.common import FlagSpec, MinorSpec
from app.ai.tasks.score_teachback.schema import ScoreTeachbackInput
from app.rules.decisions import ReportKind, decide
from app.rules.symptoms import analyse_symptom
from app.rules.teachback import passes, score_teachback

SEED = json.loads((Path(__file__).parents[1] / "app/seed/templates.json").read_text("utf-8"))
CATARACT = next(t for t in SEED if t["condition"] == "cataract")
FLAGS = [FlagSpec.model_validate(f) for f in CATARACT["red_flags"]]
MINORS = [MinorSpec.model_validate(m) for m in CATARACT["minor_symptoms"]]


def analyse(text: str, lang: str, en: str | None = None) -> Symptom:
    return analyse_symptom(
        AnalyseSymptomInput(
            transcript_native=text,
            transcript_en=en,
            language=lang,
            red_flags=FLAGS,
            minor_symptoms=MINORS,
            recovery_day=3,
        )
    )


# --- Symptom analyser -------------------------------------------------------


def test_demo_phrase_reads_back_in_kannada_and_reports_in_english() -> None:
    s = analyse("Kannu tumba kempagide, novu ide", "kn")
    assert s.read_back_native == "ನೀವು ಹೇಳಿದ್ದು: ತುಂಬಾ ಕೆಂಪು ಮತ್ತು ನೋವು. ಇದು ಸರಿಯೇ?"
    assert s.summary_en.startswith("Patient reports redness, pain")
    assert "recovery day 3" in s.summary_en
    assert s.symptoms[0].severity_words == "tumba"
    assert s.symptoms[0].body_part == "eye"
    assert s.confidence == "high"


def test_read_back_follows_the_patient_language() -> None:
    assert analyse("vali illa, konjam arippu irukku", "ta").read_back_native.startswith(
        "நீங்கள் சொன்னது"
    )
    assert analyse("aankh laal hai", "hi").read_back_native.startswith("आपने बताया")


def test_minor_remedy_is_the_templates_text() -> None:
    s = analyse("Mild itching, no pain", "en")
    template_text = next(m.remedy_en for m in MINORS if m.id == "ms_itching")
    assert [r.model_dump() for r in s.suggested_remedies] == [
        {"minor_id": "ms_itching", "remedy_en": template_text}
    ]


def test_nothing_recognised_gives_a_general_read_back() -> None:
    s = analyse("When can I take a bath?", "en")
    assert s.symptoms == [] and s.matched_flag_ids == []
    assert s.read_back_native == "I will send what you said to your doctor. Is that right?"
    assert 'Patient says: "When can I take a bath?"' in s.summary_en


def test_unplaced_symptom_lowers_confidence() -> None:
    # Fever is not on the cataract template: unknown territory, so escalate.
    s = analyse("I have fever", "en")
    assert s.matched_flag_ids == [] and s.confidence == "low"


def test_english_translation_is_also_searched() -> None:
    s = analyse("ಏನೋ ಆಗಿದೆ", "kn", en="My eye is red")
    assert s.matched_flag_ids == ["rf_redness"]


def test_duration_and_onset_are_picked_up() -> None:
    s = analyse("eye pain since yesterday, 2 days", "en")
    assert s.symptoms[0].onset == "yesterday"
    assert s.symptoms[0].duration == "2 days"


# --- Decision rules ---------------------------------------------------------


def symptom(**kw: object) -> Symptom:
    base: dict[str, object] = {"summary_en": "x", "read_back_native": "x", "confidence": "high"}
    return Symptom.model_validate(base | kw)


def test_red_flag_is_an_alert() -> None:
    assert decide(symptom(matched_flag_ids=["rf_redness"]), MINORS, 0.9).type is ReportKind.alert


def test_low_confidence_is_an_alert() -> None:
    d = decide(symptom(confidence="low", matched_minor_ids=["ms_itching"]), MINORS, 0.9)
    assert d.type is ReportKind.alert and d.reasons == ["low_confidence"]


@pytest.mark.parametrize(
    ("stt", "kind"), [(0.59, ReportKind.alert), (0.6, ReportKind.minor), (None, ReportKind.minor)]
)
def test_low_stt_confidence_is_an_alert(stt: float | None, kind: ReportKind) -> None:
    assert decide(symptom(matched_minor_ids=["ms_itching"]), MINORS, stt).type is kind


def test_minor_remedies_always_come_from_the_template() -> None:
    llm_said = symptom(
        matched_minor_ids=["ms_itching"],
        suggested_remedies=[{"minor_id": "ms_itching", "remedy_en": "Apply honey to the eye"}],
    )
    d = decide(llm_said, MINORS, 0.9)
    assert d.type is ReportKind.minor
    assert d.remedies[0].remedy_en == next(m.remedy_en for m in MINORS if m.id == "ms_itching")


def test_unknown_minor_id_is_dropped() -> None:
    assert (
        decide(symptom(matched_minor_ids=["ms_invented"]), MINORS, 0.9).type is ReportKind.general
    )


def test_nothing_matched_is_general() -> None:
    assert decide(symptom(), MINORS, 0.9).type is ReportKind.general


# --- Teach-back -------------------------------------------------------------


@pytest.mark.parametrize(
    ("mentioned", "total", "expected"),
    [
        (0, 4, False),
        (74, 100, False),
        (75, 100, True),
        (3, 4, True),
        (100, 100, True),
        (0, 0, True),
    ],
)
def test_pass_threshold_is_exact(mentioned: int, total: int, expected: bool) -> None:
    assert passes(mentioned, total, 0.75) is expected


def teachback(answer: str, lang: str) -> list[str]:
    result = score_teachback(
        ScoreTeachbackInput(answer_native=answer, language=lang, red_flags=FLAGS)
    )
    assert sorted(result.mentioned_flag_ids + result.missed_flag_ids) == sorted(f.id for f in FLAGS)
    return result.mentioned_flag_ids


def test_teachback_partial_answer_in_kannada() -> None:
    mentioned = teachback("kannu kempagidre athava novu bandre", "kn")
    assert mentioned == ["rf_eye_pain", "rf_redness"]


def test_teachback_full_answer_in_english_passes() -> None:
    answer = (
        "If my vision goes or gets blurry, if there is pain or redness, pus from the eye, "
        "flashes of light, or vomiting"
    )
    result = score_teachback(
        ScoreTeachbackInput(answer_native=answer, language="en", red_flags=FLAGS)
    )
    assert result.missed_flag_ids == [] and result.passed


def test_teachback_counts_mentions_even_when_phrased_negatively() -> None:
    assert "rf_vision_loss" in teachback("come back if I can't see", "en")


def test_teachback_empty_answer_fails() -> None:
    result = score_teachback(ScoreTeachbackInput(answer_native="", language="ta", red_flags=FLAGS))
    assert result.mentioned_flag_ids == [] and not result.passed
