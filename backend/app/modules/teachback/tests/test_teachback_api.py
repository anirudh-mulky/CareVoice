import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import models as m
from app.core.db import Database
from app.core.events import TEACHBACK_SCORED
from app.modules.demo.service import seed_id

RAMESH = (
    "Ramesh, 68, cataract right eye, standard template, "
    "diabetic so check sugar daily, language Kannada."
)
PARTIAL = "kannu kempagidre, novu jaasti aadre bartini"  # redness + pain: 2 of 6
REST = "kaanisuttilla andre, keevu, minchu, vaanti aadre bartini"  # the other 4
FULL = "kaanisuttilla andre, novu, kempu, keevu, minchu, vaanti aadre bartini"
NOTHING = "gottilla"  # "I don't know"


def db_of(client: TestClient) -> Database:
    database: Database = client.app.state.db  # type: ignore[attr-defined]
    return database


def approve(client: TestClient, transcript: str = RAMESH) -> str:
    card = client.post("/api/v1/discharges/extract", json={"transcript": transcript}).json()["card"]
    draft = client.post("/api/v1/discharges", json=card).json()
    assert client.post(f"/api/v1/discharges/{draft['id']}/approve").status_code == 200
    discharge_id: str = draft["id"]
    return discharge_id


def tokens(client: TestClient, discharge_id: str) -> dict[str, str]:
    res = client.post(f"/api/v1/delivery/discharges/{discharge_id}/links")
    return {link["recipient_type"]: link["url"].removeprefix("/p/") for link in res.json()}


def say(client: TestClient, token: str, text: str) -> dict[str, Any]:
    res = client.post(f"/api/v1/patient/{token}/teachback", json={"transcript": text})
    assert res.status_code == 200, res.text
    body: dict[str, Any] = res.json()
    return body


def status_of(client: TestClient, discharge_id: str) -> str:
    status: str = client.get(f"/api/v1/discharges/{discharge_id}").json()["status"]
    return status


def dashboard_status(client: TestClient, discharge_id: str) -> str:
    row = next(i for i in client.get("/api/v1/discharges").json() if i["id"] == discharge_id)
    status: str = row["status"]
    return status


@pytest.fixture
def ramesh(client: TestClient) -> tuple[str, str]:
    discharge_id = approve(client)
    return discharge_id, tokens(client, discharge_id)["patient"]


def test_the_question_follows_the_care_card_in_kannada(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    _, token = ramesh
    messages = client.get(f"/api/v1/patient/{token}/messages").json()
    assert [msg["kind"] for msg in messages] == ["instructions", "teachback_q"]
    question = messages[1]
    assert question["language"] == "kn"
    assert question["text"] == "ನಿಮ್ಮ ಮಾತಿನಲ್ಲೇ ಹೇಳಿ: ಯಾವಾಗ ಆಸ್ಪತ್ರೆಗೆ ಮತ್ತೆ ಬರಬೇಕು?"
    assert question["text_en"].startswith("Tell me in your own words")

    state = client.get(f"/api/v1/patient/{token}/teachback").json()
    assert state["question"] == question["text"]
    assert (state["complete"], state["tries_used"], state["max_tries"]) == (False, 0, 2)
    assert state["last"] is None


def test_a_partial_answer_re_explains_the_missed_flags(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    discharge_id, token = ramesh
    result = say(client, token, PARTIAL)
    assert result["outcome"] == "try_again" and result["passed"] is False
    assert [f["id"] for f in result["mentioned"]] == ["rf_eye_pain", "rf_redness"]
    missed = [f["id"] for f in result["missed"]]
    assert missed == ["rf_vision_loss", "rf_discharge", "rf_flashes", "rf_vomiting"]
    # Re-explained in Kannada with the template's own wording, then asked again.
    assert result["missed"][0]["label"] == "ದೃಷ್ಟಿ ಇದ್ದಕ್ಕಿದ್ದಂತೆ ಕಡಿಮೆಯಾದರೆ ಅಥವಾ ಕಾಣಿಸದಿದ್ದರೆ"
    assert result["reply"].startswith("ಈ ಎಚ್ಚರಿಕೆಯ ಲಕ್ಷಣಗಳನ್ನೂ ನೆನಪಿಡಿ")
    assert "ದೃಷ್ಟಿ ಇದ್ದಕ್ಕಿದ್ದಂತೆ" in result["reply"] and "ಕೆಂಪಾಗುತ್ತಿದ್ದರೆ" not in result["reply"]
    assert result["reply"].endswith("ಈಗ ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ: ಯಾವಾಗ ಆಸ್ಪತ್ರೆಗೆ ಮತ್ತೆ ಬರಬೇಕು?")
    assert status_of(client, discharge_id) == "sent"

    kinds = [msg["kind"] for msg in client.get(f"/api/v1/patient/{token}/messages").json()]
    assert kinds == ["instructions", "teachback_q", "teachback_a", "teachback_q"]


def test_a_full_answer_marks_understood_on_the_dashboard(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    discharge_id, token = ramesh
    result = say(client, token, FULL)
    assert result["outcome"] == "understood" and result["missed"] == []
    assert result["reply"] == "ಚೆನ್ನಾಗಿದೆ. ನಿಮಗೆ ಎಚ್ಚರಿಕೆಯ ಲಕ್ಷಣಗಳು ಗೊತ್ತಿವೆ."
    assert result["discharge_status"] == "understood"
    assert dashboard_status(client, discharge_id) == "understood"
    assert client.get(f"/api/v1/patient/{token}/teachback").json()["complete"] is True


def test_the_second_try_only_needs_the_missed_flags(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    discharge_id, token = ramesh
    say(client, token, PARTIAL)
    result = say(client, token, REST)
    assert result["try_number"] == 2
    assert result["outcome"] == "understood"
    assert len(result["mentioned"]) == 6
    assert dashboard_status(client, discharge_id) == "understood"


def test_two_failures_mark_needs_follow_up(client: TestClient, ramesh: tuple[str, str]) -> None:
    discharge_id, token = ramesh
    assert say(client, token, NOTHING)["outcome"] == "try_again"
    result = say(client, token, PARTIAL)
    assert result["outcome"] == "needs_followup"
    assert result["reply"].startswith("ಧನ್ಯವಾದ")
    assert dashboard_status(client, discharge_id) == "needs_followup"
    # No third try.
    res = client.post(f"/api/v1/patient/{token}/teachback", json={"transcript": FULL})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "teachback_complete"


def test_passing_with_a_missed_flag_still_re_explains_it(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    _, token = ramesh
    # 5 of 6 = 83%, above the 75% threshold, but vomiting is still re-explained.
    result = say(client, token, "kaanisuttilla andre, novu, kempu, keevu, minchu aadre")
    assert result["outcome"] == "understood"
    assert [f["id"] for f in result["missed"]] == ["rf_vomiting"]
    assert result["reply"].startswith("ಚೆನ್ನಾಗಿದೆ. ಇದನ್ನೂ ನೆನಪಿಡಿ: ")
    assert "ವಾಂತಿ" in result["reply"]


def test_every_try_publishes_teachback_scored(client: TestClient, ramesh: tuple[str, str]) -> None:
    discharge_id, token = ramesh
    say(client, token, PARTIAL)
    say(client, token, REST)
    with db_of(client).session() as s:
        events = list(
            s.scalars(
                select(m.Event)
                .where(
                    m.Event.type == TEACHBACK_SCORED,
                    m.Event.discharge_id == uuid.UUID(discharge_id),
                )
                .order_by(m.Event.created_at)
            )
        )
    assert [e.payload["outcome"] for e in events] == ["try_again", "understood"]
    assert events[0].actor_type is m.ActorType.patient
    assert events[1].payload["status_before"] == "sent"
    assert events[1].payload["status_after"] == "understood"
    assert events[0].payload["source"] == "rules"


def test_the_carer_can_answer_for_the_patient(client: TestClient) -> None:
    discharge_id = approve(client)
    carer = tokens(client, discharge_id)["carer"]
    assert say(client, carer, FULL)["outcome"] == "understood"
    with db_of(client).session() as s:
        event = s.scalars(
            select(m.Event).where(
                m.Event.type == TEACHBACK_SCORED, m.Event.discharge_id == uuid.UUID(discharge_id)
            )
        ).one()
    assert event.actor_type is m.ActorType.carer


def test_teach_back_never_overwrites_an_alert(client: TestClient, ramesh: tuple[str, str]) -> None:
    discharge_id, token = ramesh
    with db_of(client).session() as s:
        d = s.get(m.Discharge, uuid.UUID(discharge_id))
        assert d is not None
        d.status = m.DischargeStatus.alert
    assert say(client, token, FULL)["outcome"] == "understood"
    assert status_of(client, discharge_id) == "alert"


def test_english_answers_also_count(client: TestClient, ramesh: tuple[str, str]) -> None:
    _, token = ramesh
    result = say(client, token, "If I cannot see, pain, redness, pus, flashes or vomiting")
    assert result["outcome"] == "understood"


def test_a_blank_answer_is_rejected(client: TestClient, ramesh: tuple[str, str]) -> None:
    _, token = ramesh
    res = client.post(f"/api/v1/patient/{token}/teachback", json={"transcript": "   "})
    assert res.status_code == 422
    assert client.get(f"/api/v1/patient/{token}/teachback").json()["tries_used"] == 0


def test_a_bad_link_cannot_answer(client: TestClient) -> None:
    res = client.post("/api/v1/patient/not-a-real-token-123/teachback", json={"transcript": FULL})
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "link_invalid"


def test_a_seeded_understood_episode_is_complete(client: TestClient) -> None:
    sunita = str(seed_id("discharge:sunita"))
    token = tokens(client, sunita)["patient"]
    state = client.get(f"/api/v1/patient/{token}/teachback").json()
    assert state["complete"] is True and state["discharge_status"] == "understood"
    assert state["language"] == "hi"
