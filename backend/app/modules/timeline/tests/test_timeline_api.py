import uuid
from datetime import datetime
from typing import Any

from fastapi.testclient import TestClient

from app.core.db import Database
from app.core.events import DomainEvent
from app.modules.demo.service import seed_id

RAMESH = (
    "Ramesh, 68, cataract right eye, standard template, "
    "diabetic so check sugar daily, language Kannada."
)
PARTIAL = "kannu kempagidre, novu jaasti aadre bartini"
REST = "kaanisuttilla andre, keevu, minchu, vaanti aadre bartini"


def db_of(client: TestClient) -> Database:
    database: Database = client.app.state.db  # type: ignore[attr-defined]
    return database


def full_episode(client: TestClient) -> str:
    """Approve -> play card -> teach-back twice -> day 3 reminder -> red-flag report ->
    doctor opens it, replies, handles the alert -> close."""
    card = client.post("/api/v1/discharges/extract", json={"transcript": RAMESH}).json()["card"]
    discharge_id: str = client.post("/api/v1/discharges", json=card).json()["id"]
    client.post(f"/api/v1/discharges/{discharge_id}/approve")
    links = client.post(f"/api/v1/delivery/discharges/{discharge_id}/links").json()
    token = next(x for x in links if x["recipient_type"] == "patient")["url"].removeprefix("/p/")

    note = client.get(f"/api/v1/patient/{token}/messages").json()[0]
    client.post(f"/api/v1/patient/{token}/messages/{note['id']}/played")
    client.post(f"/api/v1/patient/{token}/teachback", json={"transcript": PARTIAL})
    client.post(f"/api/v1/patient/{token}/teachback", json={"transcript": REST})
    client.post("/api/v1/demo/advance-day")
    client.post("/api/v1/demo/advance-day")

    first = client.post(
        f"/api/v1/patient/{token}/reports", json={"transcript": "Kannu tumba kempagide, novu ide."}
    ).json()["report_id"]
    client.post(f"/api/v1/patient/{token}/reports/{first}/confirm", json={"answer": False})
    rid = client.post(
        f"/api/v1/patient/{token}/reports", json={"transcript": "Kannu tumba kempagide, novu ide."}
    ).json()["report_id"]
    client.post(f"/api/v1/patient/{token}/reports/{rid}/confirm", json={"answer": True})
    client.patch(f"/api/v1/reports/{rid}", json={"status": "seen"})
    client.post(f"/api/v1/reports/{rid}/reply", json={"text": "I will call you in the next hour."})
    client.post(f"/api/v1/discharges/{discharge_id}/alert/handled")
    client.post(f"/api/v1/discharges/{discharge_id}/close")
    return discharge_id


def timeline(client: TestClient, discharge_id: str) -> dict[str, Any]:
    res = client.get(f"/api/v1/timeline/discharges/{discharge_id}")
    assert res.status_code == 200, res.text
    body: dict[str, Any] = res.json()
    return body


def test_the_timeline_lists_every_step_with_times(client: TestClient) -> None:
    discharge_id = full_episode(client)
    body = timeline(client, discharge_id)
    assert body["patient_name"] == "Ramesh" and body["status"] == "closed"
    titles = [e["title"] for e in body["entries"]]

    expected_in_order = [
        "Discharge approved; care card sent to patient and carer",
        "Care card sent",
        "Teach-back question sent",
        "Patient played the care card",
        "Teach-back try 1 (patient): named 2 of 6 warning signs, missed signs re-explained",
        "Teach-back try 2 (patient): named 6 of 6 warning signs, understood",
        "Demo: moved to recovery day 2",
        "Demo: moved to recovery day 3",
        "Reminder sent (day 3, 09:00)",
        "Patient said the read-back was wrong and was asked again",
        "Patient reported a symptom and confirmed the read-back (alert)",
        "Safety message sent",
        "Alert raised: dashboard turned red",
        "Doctor opened the report",
        "Doctor replied",
        "Doctor marked the alert handled (now understood)",
        "Care episode closed; patient and carer links stopped working",
    ]
    positions = [titles.index(t) for t in expected_in_order]
    assert positions == sorted(positions), titles

    # Every entry has a time, in order.
    times = [datetime.fromisoformat(e["at"]) for e in body["entries"]]
    assert times == sorted(times)

    by_title = {e["title"]: e for e in body["entries"]}
    reminder = by_title["Reminder sent (day 3, 09:00)"]
    assert reminder["detail"].startswith("Time for your eye drops")
    assert by_title[
        "Teach-back try 1 (patient): named 2 of 6 warning signs, missed signs re-explained"
    ]["detail"].startswith("Missed: Sudden drop or loss of vision")
    report = by_title["Patient reported a symptom and confirmed the read-back (alert)"]
    assert report["tone"] == "danger" and report["report_id"]
    assert report["detail"].startswith("Patient reports redness, pain")
    assert by_title["Alert raised: dashboard turned red"]["detail"] == (
        "Red flags: Increasing eye pain that painkillers do not relieve; "
        "Increasing redness of the eye"
    )
    assert (
        by_title["Doctor replied"]["detail"]
        == "Your doctor says: I will call you in the next hour."
    )
    assert by_title["Doctor replied"]["actor"] == "doctor"


def test_messages_are_not_listed_twice(client: TestClient) -> None:
    discharge_id = full_episode(client)
    titles = [e["title"] for e in timeline(client, discharge_id)["entries"]]
    assert "Doctor's reply sent" not in titles and "Reminder sent" not in titles


def test_the_seeded_history_reads_well(client: TestClient) -> None:
    body = timeline(client, str(seed_id("discharge:murugan")))
    titles = [e["title"] for e in body["entries"]]
    assert titles[0] == "Discharge approved; care card sent to patient and carer"
    assert "Patient reported a symptom and confirmed the read-back (alert)" in titles
    assert "Alert raised: dashboard turned red" in titles


def test_a_new_event_type_still_appears(client: TestClient) -> None:
    sunita = str(seed_id("discharge:sunita"))
    with db_of(client).session() as s:
        client.app.state.bus.publish(  # type: ignore[attr-defined]
            s,
            DomainEvent(type="sms.delivered", discharge_id=uuid.UUID(sunita)),
        )
    titles = [e["title"] for e in timeline(client, sunita)["entries"]]
    assert titles[-1] == "Sms delivered"


def test_unknown_discharge_is_404(client: TestClient) -> None:
    res = client.get("/api/v1/timeline/discharges/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404
