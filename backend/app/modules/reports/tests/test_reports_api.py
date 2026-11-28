import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import models as m
from app.core.db import Database
from app.core.events import REPORT_CONFIRMED, REPORT_REJECTED, DomainEvent
from app.modules.demo.service import seed_id

RAMESH = (
    "Ramesh, 68, cataract right eye, standard template, "
    "diabetic so check sugar daily, language Kannada."
)
RED_EYE = "Kannu tumba kempagide, novu ide."
ITCH = "kannu turike ide"  # itching: a minor symptom in the cataract template


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


def speak(client: TestClient, token: str, text: str, **extra: Any) -> dict[str, Any]:
    res = client.post(f"/api/v1/patient/{token}/reports", json={"transcript": text, **extra})
    assert res.status_code == 201, res.text
    body: dict[str, Any] = res.json()
    return body


def confirm(client: TestClient, token: str, report_id: str, **body: Any) -> dict[str, Any]:
    res = client.post(f"/api/v1/patient/{token}/reports/{report_id}/confirm", json=body)
    assert res.status_code == 200, res.text
    out: dict[str, Any] = res.json()
    return out


def doctor_ids(client: TestClient) -> set[str]:
    return {r["id"] for r in client.get("/api/v1/reports").json()}


@pytest.fixture
def ramesh(client: TestClient) -> tuple[str, str]:
    discharge_id = approve(client)
    return discharge_id, tokens(client, discharge_id)["patient"]


def test_the_kannada_red_eye_phrase_is_read_back_in_kannada(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    _, token = ramesh
    read_back = speak(client, token, RED_EYE)
    assert read_back["language"] == "kn"
    assert read_back["read_back"] == "ನೀವು ಹೇಳಿದ್ದು: ತುಂಬಾ ಕೆಂಪು ಮತ್ತು ನೋವು. ಇದು ಸರಿಯೇ?"
    # Nothing reaches the doctor before the patient says yes.
    assert read_back["report_id"] not in doctor_ids(client)


def test_yes_sends_an_english_report_the_doctor_can_read(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    discharge_id, token = ramesh
    received: list[DomainEvent] = []
    client.app.state.bus.subscribe(REPORT_CONFIRMED, lambda e, _s: received.append(e))  # type: ignore[attr-defined]
    report_id = speak(client, token, RED_EYE)["report_id"]
    out = confirm(client, token, report_id, answer=True)
    assert out["outcome"] == "sent"
    assert out["message"].startswith("ಧನ್ಯವಾದ")

    listed = client.get("/api/v1/reports").json()
    assert listed[0]["id"] == report_id and listed[0]["type"] == "alert"
    report = client.get(f"/api/v1/reports/{report_id}").json()
    assert report["patient_name"] == "Ramesh"
    assert report["transcript_native"] == RED_EYE
    assert report["translation_en"] == "My eye is very red, and there is pain."
    assert report["summary_en"].startswith("Patient reports redness, pain")
    assert report["recovery_day"] == 1
    assert {f["id"] for f in report["red_flags"]} == {"rf_redness", "rf_eye_pain"}
    assert "red_flag" in report["reasons"]
    assert [s["name_en"] for s in report["symptoms"]] == ["redness", "pain"]
    assert report["medicines"][0]["name"] == "Moxifloxacin 0.5% eye drops"
    assert report["medicines"][0]["instructions"] == "1 drop, 4 times a day, 7 days"
    assert report["extra_instructions"] == ["Diabetic so check sugar daily"]
    assert report["reported_by"] == "patient" and report["status"] == "new"

    assert len(received) == 1
    assert received[0].payload["type"] == "alert"
    assert received[0].discharge_id == uuid.UUID(discharge_id)
    # The patient's words are in the chat, for the doctor.
    chat = client.get(f"/api/v1/patient/{token}/messages").json()
    words = next(msg for msg in chat if msg["kind"] == "report")
    assert words["direction"] == "to_doctor" and words["text"] == RED_EYE


def test_no_asks_again_and_the_doctor_never_sees_it(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    _, token = ramesh
    report_id = speak(client, token, RED_EYE)["report_id"]
    out = confirm(client, token, report_id, answer=False)
    assert out["outcome"] == "say_again"
    assert out["message"] == "ಕ್ಷಮಿಸಿ. ಏನು ತೊಂದರೆ ಎಂದು ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ."
    assert report_id not in doctor_ids(client)
    assert client.get(f"/api/v1/reports/{report_id}").status_code == 404
    # It cannot be confirmed afterwards; the patient says it again instead.
    res = client.post(f"/api/v1/patient/{token}/reports/{report_id}/confirm", json={"answer": True})
    assert res.status_code == 409
    second = speak(client, token, RED_EYE)["report_id"]
    assert confirm(client, token, second, answer=True)["outcome"] == "sent"
    assert doctor_ids(client) >= {second}
    with db_of(client).session() as s:
        rejected = s.scalars(select(m.Event).where(m.Event.type == REPORT_REJECTED)).one()
        assert rejected.payload["report_id"] == report_id


def test_spoken_yes_and_no(client: TestClient, ramesh: tuple[str, str]) -> None:
    _, token = ramesh
    first = speak(client, token, RED_EYE)["report_id"]
    assert confirm(client, token, first, transcript="illa, tappu")["outcome"] == "say_again"
    second = speak(client, token, RED_EYE)["report_id"]
    assert confirm(client, token, second, transcript="hmm")["outcome"] == "unclear"
    assert confirm(client, token, second, transcript="ಹೌದು")["outcome"] == "sent"


def test_a_double_tap_on_yes_sends_once(client: TestClient, ramesh: tuple[str, str]) -> None:
    _, token = ramesh
    received: list[DomainEvent] = []
    client.app.state.bus.subscribe(REPORT_CONFIRMED, lambda e, _s: received.append(e))  # type: ignore[attr-defined]
    report_id = speak(client, token, RED_EYE)["report_id"]
    confirm(client, token, report_id, answer=True)
    assert confirm(client, token, report_id, answer=True)["outcome"] == "sent"
    assert len(received) == 1


def test_a_minor_symptom_gets_the_templates_remedy(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    _, token = ramesh
    report_id = speak(client, token, ITCH)["report_id"]
    confirm(client, token, report_id, answer=True)
    report = client.get(f"/api/v1/reports/{report_id}").json()
    assert report["type"] == "minor"
    assert [r["minor_id"] for r in report["suggested_remedies"]] == ["ms_itching"]
    with db_of(client).session() as s:
        tpl = s.get(m.Template, (seed_id("template:cataract"), 1))
        assert tpl is not None
        remedy = next(x["remedy_en"] for x in tpl.minor_symptoms if x["id"] == "ms_itching")
    assert report["suggested_remedies"][0]["remedy_en"] == remedy


def test_low_speech_confidence_escalates(client: TestClient, ramesh: tuple[str, str]) -> None:
    _, token = ramesh
    report_id = speak(client, token, ITCH, stt_confidence=0.4)["report_id"]
    confirm(client, token, report_id, answer=True)
    report = client.get(f"/api/v1/reports/{report_id}").json()
    assert report["type"] == "alert" and "low_stt_confidence" in report["reasons"]


def test_a_carer_report_is_marked_as_such(client: TestClient) -> None:
    discharge_id = approve(client)
    carer = tokens(client, discharge_id)["carer"]
    report_id = speak(client, carer, RED_EYE)["report_id"]
    confirm(client, carer, report_id, answer=True)
    assert client.get(f"/api/v1/reports/{report_id}").json()["reported_by"] == "carer"


def test_another_patients_link_cannot_confirm(client: TestClient, ramesh: tuple[str, str]) -> None:
    _, token = ramesh
    report_id = speak(client, token, RED_EYE)["report_id"]
    other = tokens(client, str(seed_id("discharge:sunita")))["patient"]
    res = client.post(f"/api/v1/patient/{other}/reports/{report_id}/confirm", json={"answer": True})
    assert res.status_code == 404


def test_confirm_needs_an_answer(client: TestClient, ramesh: tuple[str, str]) -> None:
    _, token = ramesh
    report_id = speak(client, token, RED_EYE)["report_id"]
    res = client.post(f"/api/v1/patient/{token}/reports/{report_id}/confirm", json={})
    assert res.status_code == 422


def test_the_recording_is_kept_for_the_doctor(client: TestClient, ramesh: tuple[str, str]) -> None:
    _, token = ramesh
    report_id = speak(client, token, RED_EYE)["report_id"]
    url = f"/api/v1/patient/{token}/reports/{report_id}/audio"
    res = client.put(url, content=b"webm-bytes", headers={"content-type": "audio/webm;codecs=opus"})
    assert res.status_code == 204
    confirm(client, token, report_id, answer=True)
    report = client.get(f"/api/v1/reports/{report_id}").json()
    assert report["audio_url"] == f"/api/v1/reports/{report_id}/audio"
    audio = client.get(report["audio_url"])
    assert audio.status_code == 200 and audio.content == b"webm-bytes"
    assert audio.headers["content-type"] == "audio/webm"
    # Only once, only audio, not too big.
    assert client.put(url, content=b"x", headers={"content-type": "audio/webm"}).status_code == 409
    other = speak(client, token, RED_EYE)["report_id"]
    other_url = f"/api/v1/patient/{token}/reports/{other}/audio"
    bad = client.put(other_url, content=b"x", headers={"content-type": "text/plain"})
    assert bad.status_code == 415
    big = client.put(other_url, content=b"x" * 2_000_001, headers={"content-type": "audio/webm"})
    assert big.status_code == 413


def test_audio_sent_after_yes_reaches_the_chat_message(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    _, token = ramesh
    report_id = speak(client, token, RED_EYE)["report_id"]
    confirm(client, token, report_id, answer=True)
    client.put(
        f"/api/v1/patient/{token}/reports/{report_id}/audio",
        content=b"late",
        headers={"content-type": "audio/ogg"},
    )
    chat = client.get(f"/api/v1/patient/{token}/messages").json()
    words = next(msg for msg in chat if msg["kind"] == "report")
    assert words["audio_url"] == f"/api/v1/reports/{report_id}/audio"


def test_marking_seen(client: TestClient, ramesh: tuple[str, str]) -> None:
    _, token = ramesh
    report_id = speak(client, token, RED_EYE)["report_id"]
    confirm(client, token, report_id, answer=True)
    res = client.patch(f"/api/v1/reports/{report_id}", json={"status": "seen"})
    assert res.status_code == 200 and res.json()["status"] == "seen"
    assert (
        client.patch(f"/api/v1/reports/{report_id}", json={"status": "replied"}).status_code == 422
    )


def test_the_doctor_list_puts_alerts_first(client: TestClient) -> None:
    listed = client.get("/api/v1/reports").json()
    assert [r["patient_name"] for r in listed] == ["Murugan", "Sunita"]
    assert [r["type"] for r in listed] == ["alert", "minor"]
    minors = client.get("/api/v1/reports", params={"type": "minor"}).json()
    assert [r["patient_name"] for r in minors] == ["Sunita"]


def test_dashboard_search_and_report_counts(client: TestClient, ramesh: tuple[str, str]) -> None:
    discharge_id, token = ramesh
    report_id = speak(client, token, RED_EYE)["report_id"]
    confirm(client, token, report_id, answer=True)
    found = client.get("/api/v1/discharges", params={"q": "rame"}).json()
    assert [d["patient_name"] for d in found] == ["Ramesh"]
    row = found[0]
    assert row["id"] == discharge_id
    assert (row["new_reports"], row["latest_report_id"], row["latest_report_type"]) == (
        1,
        report_id,
        "alert",
    )
    assert client.get("/api/v1/discharges", params={"q": "nobody"}).json() == []


def test_a_closed_episode_takes_no_reports(client: TestClient, ramesh: tuple[str, str]) -> None:
    discharge_id, token = ramesh
    with db_of(client).session() as s:
        d = s.get(m.Discharge, uuid.UUID(discharge_id))
        assert d is not None
        d.status = m.DischargeStatus.closed
    res = client.post(f"/api/v1/patient/{token}/reports", json={"transcript": RED_EYE})
    assert res.status_code == 409
