import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.channels.in_app import InAppChannel
from app.core import models as m
from app.core.db import Database
from app.core.events import (
    ALERT_HANDLED,
    DOCTOR_REPLIED,
    EPISODE_CLOSED,
    REMEDY_APPROVED,
    REPORT_ALERT,
)
from app.modules.demo.service import seed_id

RAMESH = (
    "Ramesh, 68, cataract right eye, standard template, "
    "diabetic so check sugar daily, language Kannada."
)
RED_EYE = "Kannu tumba kempagide, novu ide."
ITCH = "kannu turike ide"
QUESTION = "naale check-up ge barabeka?"  # "should I come for the check-up tomorrow?"
SAFETY_KN = "ನೀವು ಹೇಳಿದ್ದು ಮುಖ್ಯವಾದ ಎಚ್ಚರಿಕೆಯ ಲಕ್ಷಣ ಆಗಿರಬಹುದು. ದಯವಿಟ್ಟು ಇಂದೇ ಆಸ್ಪತ್ರೆಗೆ ಬನ್ನಿ."


def db_of(client: TestClient) -> Database:
    database: Database = client.app.state.db  # type: ignore[attr-defined]
    return database


def approve(client: TestClient) -> str:
    card = client.post("/api/v1/discharges/extract", json={"transcript": RAMESH}).json()["card"]
    draft = client.post("/api/v1/discharges", json=card).json()
    assert client.post(f"/api/v1/discharges/{draft['id']}/approve").status_code == 200
    discharge_id: str = draft["id"]
    return discharge_id


def tokens(client: TestClient, discharge_id: str) -> dict[str, str]:
    res = client.post(f"/api/v1/delivery/discharges/{discharge_id}/links")
    return {link["recipient_type"]: link["url"].removeprefix("/p/") for link in res.json()}


def report(client: TestClient, token: str, text: str, **extra: Any) -> str:
    rid: str = client.post(
        f"/api/v1/patient/{token}/reports", json={"transcript": text, **extra}
    ).json()["report_id"]
    res = client.post(f"/api/v1/patient/{token}/reports/{rid}/confirm", json={"answer": True})
    assert res.json()["outcome"] == "sent", res.text
    return rid


def chat(client: TestClient, token: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = client.get(f"/api/v1/patient/{token}/messages").json()
    return messages


def status_of(client: TestClient, discharge_id: str) -> str:
    row = next(i for i in client.get("/api/v1/discharges").json() if i["id"] == discharge_id)
    status: str = row["status"]
    return status


def events(client: TestClient, kind: str, discharge_id: str) -> list[m.Event]:
    with db_of(client).session() as s:
        return list(
            s.scalars(
                select(m.Event)
                .where(m.Event.type == kind, m.Event.discharge_id == uuid.UUID(discharge_id))
                .order_by(m.Event.created_at)
            )
        )


@pytest.fixture
def ramesh(client: TestClient) -> tuple[str, str]:
    discharge_id = approve(client)
    return discharge_id, tokens(client, discharge_id)["patient"]


# --- Alert branch ---------------------------------------------------------------------------


def test_a_red_flag_turns_the_dashboard_red_and_tells_the_patient_to_come_today(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    discharge_id, token = ramesh
    channel: InAppChannel = client.app.state.channels.channels["in_app"]  # type: ignore[attr-defined]
    channel.delivered.clear()
    report(client, token, RED_EYE)

    assert status_of(client, discharge_id) == "alert"
    assert client.get("/api/v1/discharges").json()[0]["id"] == discharge_id  # alerts first
    safety = chat(client, token)[-1]
    assert safety["kind"] == "safety" and safety["language"] == "kn"
    assert safety["text"].startswith(SAFETY_KN)
    assert safety["text_en"].startswith("What you described may be an important warning sign")
    # Patient and carer both get it, without waiting for the doctor.
    assert [d.recipient_type.value for d in channel.delivered] == ["patient", "carer"]
    alert = events(client, REPORT_ALERT, discharge_id)
    assert alert[0].payload["status_before"] == "sent"


def test_low_speech_confidence_also_alerts(client: TestClient, ramesh: tuple[str, str]) -> None:
    discharge_id, token = ramesh
    report(client, token, ITCH, stt_confidence=0.3)
    assert status_of(client, discharge_id) == "alert"
    assert chat(client, token)[-1]["kind"] == "safety"


def test_no_remedy_is_ever_sent_for_an_alert(client: TestClient, ramesh: tuple[str, str]) -> None:
    _, token = ramesh
    rid = report(client, token, RED_EYE)
    assert client.get(f"/api/v1/reports/{rid}/actions").json()["can_send_remedy"] is False
    res = client.post(f"/api/v1/reports/{rid}/remedy", json={"minor_ids": ["ms_itching"]})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "alert_needs_call"


def test_handling_the_alert_returns_to_the_status_before_it(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    discharge_id, token = ramesh
    full = "kaanisuttilla andre, novu, kempu, keevu, minchu, vaanti aadre bartini"
    client.post(f"/api/v1/patient/{token}/teachback", json={"transcript": full})
    assert status_of(client, discharge_id) == "understood"
    rid = report(client, token, RED_EYE)
    assert status_of(client, discharge_id) == "alert"

    res = client.post(f"/api/v1/discharges/{discharge_id}/alert/handled")
    assert res.status_code == 200
    assert res.json()["discharge_status"] == "understood"
    assert status_of(client, discharge_id) == "understood"
    assert client.get(f"/api/v1/reports/{rid}").json()["status"] == "seen"
    assert len(events(client, ALERT_HANDLED, discharge_id)) == 1
    again = client.post(f"/api/v1/discharges/{discharge_id}/alert/handled")
    assert again.status_code == 409


def test_the_seeded_alert_can_be_handled(client: TestClient) -> None:
    murugan = str(seed_id("discharge:murugan"))
    res = client.post(f"/api/v1/discharges/{murugan}/alert/handled")
    assert res.status_code == 200 and res.json()["discharge_status"] == "sent"


# --- Minor branch: template remedy, doctor approves -----------------------------------------


def test_a_minor_report_waits_for_the_doctor(client: TestClient, ramesh: tuple[str, str]) -> None:
    discharge_id, token = ramesh
    before = len(chat(client, token))
    rid = report(client, token, ITCH)
    # Only the patient's own words were added; nothing was sent to them.
    assert [msg["kind"] for msg in chat(client, token)[before:]] == ["report"]
    assert status_of(client, discharge_id) == "sent"

    acts = client.get(f"/api/v1/reports/{rid}/actions").json()
    assert acts["can_send_remedy"] is True and acts["language"] == "kn"
    options = {o["minor_id"]: o for o in acts["remedy_options"]}
    assert set(options) == {"ms_itching", "ms_watering", "ms_glare"}
    assert options["ms_itching"]["suggested"] is True
    assert options["ms_watering"]["suggested"] is False
    assert options["ms_itching"]["remedy_native"].startswith("ಕಣ್ಣು ಗುಣವಾಗುವಾಗ ಸ್ವಲ್ಪ ತುರಿಕೆ")
    assert options["ms_itching"]["translated"] is True


def test_the_approved_remedy_is_the_templates_own_text_in_kannada(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    discharge_id, token = ramesh
    rid = report(client, token, ITCH)
    res = client.post(f"/api/v1/reports/{rid}/remedy", json={"minor_ids": ["ms_itching"]})
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["outcome"] == "sent" and out["report_status"] == "remedy_sent"

    with db_of(client).session() as s:
        tpl = s.get(m.Template, (seed_id("template:cataract"), 1))
        kn = s.get(m.TemplateTranslation, (seed_id("template:cataract"), 1, "kn"))
        assert tpl is not None and kn is not None
        english = next(x["remedy_en"] for x in tpl.minor_symptoms if x["id"] == "ms_itching")
        native = next(x["remedy"] for x in kn.content["minor_symptoms"] if x["id"] == "ms_itching")

    remedy = chat(client, token)[-1]
    assert remedy["kind"] == "remedy" and remedy["language"] == "kn"
    assert remedy["text"] == f"ನಿಮ್ಮ ವೈದ್ಯರಿಂದ ಸಂದೇಶ: {native}"
    assert remedy["text_en"] == f"Message from your doctor: {english}"
    approved = events(client, REMEDY_APPROVED, discharge_id)
    assert approved[0].payload["minor_ids"] == ["ms_itching"]
    assert approved[0].actor_type is m.ActorType.doctor


def test_a_double_tap_sends_the_remedy_once(client: TestClient, ramesh: tuple[str, str]) -> None:
    discharge_id, token = ramesh
    rid = report(client, token, ITCH)
    url = f"/api/v1/reports/{rid}/remedy"
    assert client.post(url, json={"minor_ids": ["ms_itching"]}).json()["outcome"] == "sent"
    assert client.post(url, json={"minor_ids": ["ms_itching"]}).json()["outcome"] == "already_sent"
    assert [msg["kind"] for msg in chat(client, token)].count("remedy") == 1
    assert len(events(client, REMEDY_APPROVED, discharge_id)) == 1


def test_remedies_come_only_from_the_template(client: TestClient, ramesh: tuple[str, str]) -> None:
    _, token = ramesh
    rid = report(client, token, ITCH)
    res = client.post(f"/api/v1/reports/{rid}/remedy", json={"minor_ids": ["take_ibuprofen"]})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "not_in_template"
    # Free text is not even part of the request.
    res = client.post(f"/api/v1/reports/{rid}/remedy", json={"text": "Take ibuprofen"})
    assert res.status_code == 422


def test_the_seeded_hindi_minor_report_gets_the_hindi_remedy(client: TestClient) -> None:
    sunita = next(r for r in client.get("/api/v1/reports").json() if r["patient_name"] == "Sunita")
    res = client.post(
        f"/api/v1/reports/{sunita['id']}/remedy", json={"minor_ids": ["ms_wound_itch"]}
    )
    assert res.status_code == 200
    message = res.json()["message"]
    assert message["language"] == "hi"
    assert message["text_native"].startswith("आपके डॉक्टर का संदेश: टांके भरते समय खुजली आम है।")


# --- General branch: doctor reply -----------------------------------------------------------


def test_a_quick_reply_reaches_the_patient_in_kannada(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    discharge_id, token = ramesh
    rid = report(client, token, QUESTION)
    detail = client.get(f"/api/v1/reports/{rid}").json()
    assert detail["type"] == "general"
    assert status_of(client, discharge_id) == "sent"

    text = "Please come for your check-up on the day written on your care card."
    preview = client.post(f"/api/v1/reports/{rid}/reply/preview", json={"text": text}).json()
    assert preview == {
        "language": "kn",
        "text_native": "ನಿಮ್ಮ ಆರೈಕೆ ಕಾರ್ಡ್‌ನಲ್ಲಿ ಬರೆದ ದಿನ ತಪಾಸಣೆಗೆ ಬನ್ನಿ.",
        "translated": True,
    }
    res = client.post(f"/api/v1/reports/{rid}/reply", json={"text": text})
    assert res.json()["outcome"] == "sent" and res.json()["report_status"] == "replied"
    reply = chat(client, token)[-1]
    assert reply["kind"] == "doctor_reply" and reply["language"] == "kn"
    assert reply["text"] == "ನಿಮ್ಮ ವೈದ್ಯರು ಹೇಳುತ್ತಾರೆ: ನಿಮ್ಮ ಆರೈಕೆ ಕಾರ್ಡ್‌ನಲ್ಲಿ ಬರೆದ ದಿನ ತಪಾಸಣೆಗೆ ಬನ್ನಿ."
    assert reply["text_en"] == f"Your doctor says: {text}"
    assert events(client, DOCTOR_REPLIED, discharge_id)[0].payload["translated"] is True


def test_free_text_the_demo_cannot_translate_is_flagged_and_sent_in_english(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    _, token = ramesh
    rid = report(client, token, QUESTION)
    text = "Yes, Thursday at 10 is fine."
    preview = client.post(f"/api/v1/reports/{rid}/reply/preview", json={"text": text}).json()
    assert preview["translated"] is False and preview["text_native"] == text
    client.post(f"/api/v1/reports/{rid}/reply", json={"text": text})
    assert chat(client, token)[-1]["text"] == f"Your doctor says: {text}"


def test_a_repeated_reply_with_the_same_key_sends_once(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    discharge_id, token = ramesh
    rid = report(client, token, QUESTION)
    url = f"/api/v1/reports/{rid}/reply"
    body = {"text": "Please come to the hospital today."}
    first = client.post(url, json=body, headers={"Idempotency-Key": "k1"}).json()
    second = client.post(url, json=body, headers={"Idempotency-Key": "k1"}).json()
    assert (first["outcome"], second["outcome"]) == ("sent", "already_sent")
    assert second["message"]["id"] == first["message"]["id"]
    assert len(events(client, DOCTOR_REPLIED, discharge_id)) == 1


def test_a_blank_reply_is_rejected(client: TestClient, ramesh: tuple[str, str]) -> None:
    _, token = ramesh
    rid = report(client, token, QUESTION)
    assert client.post(f"/api/v1/reports/{rid}/reply", json={"text": "  "}).status_code == 422


def test_actions_list_what_the_patient_received(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    _, token = ramesh
    rid = report(client, token, RED_EYE)
    client.post(f"/api/v1/reports/{rid}/reply", json={"text": "I will call you in the next hour."})
    acts = client.get(f"/api/v1/reports/{rid}/actions").json()
    assert [s["kind"] for s in acts["sent"]] == ["safety", "doctor_reply"]
    assert acts["can_handle_alert"] is True
    assert len(acts["quick_replies"]) == 5


def test_an_unconfirmed_report_has_no_actions(client: TestClient, ramesh: tuple[str, str]) -> None:
    _, token = ramesh
    rid = client.post(f"/api/v1/patient/{token}/reports", json={"transcript": ITCH}).json()[
        "report_id"
    ]
    assert client.get(f"/api/v1/reports/{rid}/actions").status_code == 404
    assert client.post(f"/api/v1/reports/{rid}/reply", json={"text": "Hi"}).status_code == 404


# --- Closing the episode --------------------------------------------------------------------


def test_closing_the_episode_stops_the_links(client: TestClient, ramesh: tuple[str, str]) -> None:
    discharge_id, token = ramesh
    rid = report(client, token, QUESTION)
    res = client.post(f"/api/v1/discharges/{discharge_id}/close")
    assert res.status_code == 200 and res.json()["discharge_status"] == "closed"
    assert status_of(client, discharge_id) == "closed"
    assert client.get(f"/api/v1/patient/{token}").status_code == 404
    assert client.post(f"/api/v1/reports/{rid}/reply", json={"text": "Hi"}).status_code == 409
    assert client.get(f"/api/v1/reports/{rid}/actions").json()["can_close"] is False
    closed = events(client, EPISODE_CLOSED, discharge_id)
    # Two links from delivery and two from the doctor's "Links" button: all revoked.
    assert closed[0].payload["links_revoked"] == 4
    # Closing twice is harmless.
    assert client.post(f"/api/v1/discharges/{discharge_id}/close").status_code == 200
