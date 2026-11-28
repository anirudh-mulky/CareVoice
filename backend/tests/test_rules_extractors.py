from typing import Any

import pytest

from app.ai.tasks.common import TemplateRef
from app.ai.tasks.extract_discharge.schema import ExtractDischargeInput
from app.ai.tasks.extract_template.schema import ExtractTemplateInput
from app.rules.extractors import extract_discharge, extract_template

TEMPLATES = [
    TemplateRef(name="Cataract surgery", condition="cataract"),
    TemplateRef(name="C-section", condition="caesarean section"),
]


def discharge(text: str) -> dict[str, Any]:
    return extract_discharge(
        ExtractDischargeInput(transcript=text, templates=TEMPLATES)
    ).model_dump()


def test_the_ramesh_sentence_fills_the_card() -> None:
    assert discharge(
        "Ramesh, 68, cataract right eye, standard template, "
        "diabetic so check sugar daily, language Kannada."
    ) == {
        "patient_name": "Ramesh",
        "age": 68,
        "template_name": "Cataract surgery",
        "side": "right",
        "extra_instructions": ["Diabetic so check sugar daily"],
        "language": "kn",
        "carer_phone": None,
        "unclear_fields": [],
    }


def test_carer_phone_and_spoken_alias() -> None:
    d = discharge("Sunita, 29 years, C-section, language Hindi, husband's phone 98450 12345")
    assert d["patient_name"] == "Sunita"
    assert d["age"] == 29
    assert d["template_name"] == "C-section"
    assert d["language"] == "hi"
    assert d["carer_phone"] == "+919845012345"
    assert d["extra_instructions"] == []
    assert d["unclear_fields"] == []


def test_works_without_commas() -> None:
    d = discharge("patient Murugan 55 cataract left eye Tamil")
    assert (d["patient_name"], d["age"], d["side"], d["language"]) == ("Murugan", 55, "left", "ta")


@pytest.mark.parametrize(
    "extra",
    [
        "add timolol drops",  # no dose, no frequency
        "eye drops twice daily",  # frequency but no dose
        "prednisolone 5 or 10 mg daily",  # ambiguous dose
    ],
)
def test_unclear_doses_are_flagged_never_filled(extra: str) -> None:
    d = discharge(f"Ramesh, 68, cataract right eye, Kannada, {extra}")
    assert d["unclear_fields"] == ["extra_instructions[0]"]
    assert d["extra_instructions"] == [extra[0].upper() + extra[1:]]


def test_clear_dose_is_accepted() -> None:
    d = discharge("Sunita, 29, C-section, Hindi, paracetamol 500 mg twice daily")
    assert d["extra_instructions"] == ["Paracetamol 500 mg twice daily"]
    assert d["unclear_fields"] == []


def test_dose_numbers_are_not_read_as_age() -> None:
    d = discharge("Ravi, cataract left eye, Kannada, timolol 1 drop twice daily")
    assert d["age"] is None
    assert "age" in d["unclear_fields"]


def test_missing_and_unknown_fields_are_unclear() -> None:
    assert discharge("cataract right eye, language Kannada")["unclear_fields"] == [
        "patient_name",
        "age",
    ]
    unknown = discharge("Ravi, 50, knee replacement, language Kannada")
    assert unknown["template_name"] is None
    assert "template_name" in unknown["unclear_fields"]


def test_template_extraction_from_dictation() -> None:
    text = (
        "Template for cataract surgery. "
        "Moxifloxacin eye drops 1 drop four times a day for 7 days. "
        "Timolol drops. "
        "Wear the eye shield at night. "
        "Do not rub the eye. "
        "Come back immediately if there is sudden loss of vision, severe pain or pus. "
        "If there is mild itching, tell them to use lubricating drops. "
        "On day 3 at 9 am remind them to put eye drops. "
        "Follow up on day 7."
    )
    t = extract_template(ExtractTemplateInput(transcript=text))
    assert t.name == "Cataract surgery"
    assert t.medicines[0].dose == "1 drop"
    assert t.medicines[0].frequency == "four times a day"
    assert t.medicines[0].duration_days == 7
    assert t.unclear_fields == ["medicines[1].dose", "medicines[1].frequency"]
    assert t.dos == ["Wear the eye shield at night"]
    assert t.donts == ["Do not rub the eye"]
    assert [f.label_en for f in t.red_flags] == ["Sudden loss of vision", "Severe pain", "Pus"]
    assert t.minor_symptoms[0].symptom_en == "Mild itching"
    assert t.minor_symptoms[0].remedy_en == "Use lubricating drops"
    assert (t.reminders[0].day, t.reminders[0].time) == (3, "09:00")
    assert t.follow_up_day == 7


def test_template_without_name_or_red_flags_is_unclear() -> None:
    t = extract_template(ExtractTemplateInput(transcript="Wear dark glasses."))
    assert t.unclear_fields == ["name", "red_flags"]
