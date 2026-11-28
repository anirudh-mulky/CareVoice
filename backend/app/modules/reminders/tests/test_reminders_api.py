import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.channels.in_app import InAppChannel
from app.core import models as m
from app.core.db import Database
from app.core.events import REMINDER_DUE, REMINDERS_SCHEDULED
from app.modules.demo.service import seed_id
from app.modules.reminders import service

RAMESH = (
    "Ramesh, 68, cataract right eye, standard template, "
    "diabetic so check sugar daily, language Kannada."
)
DAY3_KN = "ಕಣ್ಣಿನ ಹನಿ ಹಾಕುವ ಸಮಯ. ನಿಮ್ಮ ಕಣ್ಣು ಕೆಂಪಾಗಿದೆಯೇ ಅಥವಾ ನೋವಿದೆಯೇ? ಮೈಕ್ ಒತ್ತಿ ಹೇಳಿ."
DAY3_EN = "Time for your eye drops. Is your eye red or painful? Tap the mic and tell me."
IST = timezone(timedelta(minutes=330))


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


def advance(client: TestClient) -> dict[str, Any]:
    res = client.post("/api/v1/demo/advance-day")
    assert res.status_code == 200, res.text
    body: dict[str, Any] = res.json()
    return body


def row(body: dict[str, Any], name: str) -> dict[str, Any]:
    found: dict[str, Any] = next(p for p in body["patients"] if p["patient_name"] == name)
    return found


def chat(client: TestClient, token: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = client.get(f"/api/v1/patient/{token}/messages").json()
    return messages


@pytest.fixture
def ramesh(client: TestClient) -> tuple[str, str]:
    discharge_id = approve(client)
    return discharge_id, tokens(client, discharge_id)["patient"]


def test_due_times_are_hospital_local() -> None:
    due = service.due_at(date(2026, 11, 28), 3, "09:00", IST)
    assert due == datetime(2026, 11, 30, 3, 30, tzinfo=UTC)  # 09:00 IST on day 3


def test_approval_schedules_the_templates_reminders(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    discharge_id, _ = ramesh
    listed = client.get(f"/api/v1/reminders/discharges/{discharge_id}").json()
    by_day = {r["day"]: r for r in listed}
    # Day 1 at 08:00 is only scheduled if it was still ahead when the patient left.
    assert {3, 6} <= set(by_day)
    assert by_day[3]["status"] == "pending" and by_day[3]["time"] == "09:00"
    assert by_day[3]["text_en"] == DAY3_EN
    with db_of(client).session() as s:
        event = s.scalars(
            select(m.Event).where(
                m.Event.type == REMINDERS_SCHEDULED,
                m.Event.discharge_id == uuid.UUID(discharge_id),
            )
        ).one()
        assert event.payload["scheduled"] == len(listed)


def test_simulating_day_3_sends_the_eye_drops_reminder_in_kannada(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    discharge_id, token = ramesh
    channel: InAppChannel = client.app.state.channels.channels["in_app"]  # type: ignore[attr-defined]

    day2 = advance(client)
    assert row(day2, "Ramesh")["recovery_day"] == 2
    assert not any(msg["text"] == DAY3_KN for msg in chat(client, token))

    channel.delivered.clear()
    day3 = advance(client)
    assert row(day3, "Ramesh") == {"patient_name": "Ramesh", "recovery_day": 3, "reminders_sent": 1}
    reminder = chat(client, token)[-1]
    assert reminder["kind"] == "reminder" and reminder["language"] == "kn"
    assert reminder["text"] == DAY3_KN and reminder["text_en"] == DAY3_EN
    assert [d.recipient_type.value for d in channel.delivered] == ["patient", "carer"]

    # Today's reminder on the patient home.
    today = client.get(f"/api/v1/patient/{token}/reminders/today").json()
    assert today["recovery_day"] == 3
    assert [(r["time"], r["text"], r["state"], r["played"]) for r in today["reminders"]] == [
        ("09:00", DAY3_KN, "sent", False)
    ]
    played = f"/api/v1/patient/{token}/messages/{reminder['id']}/played"
    assert client.post(played).status_code == 204
    today = client.get(f"/api/v1/patient/{token}/reminders/today").json()
    assert today["reminders"][0]["played"] is True
    assert client.get(f"/api/v1/patient/{token}").json()["recovery_day"] == 3

    listed = client.get(f"/api/v1/reminders/discharges/{discharge_id}").json()
    sent = next(r for r in listed if r["day"] == 3)
    assert sent["status"] == "done" and sent["message_id"] == reminder["id"]


def test_a_reminder_is_sent_once(client: TestClient, ramesh: tuple[str, str]) -> None:
    discharge_id, token = ramesh
    advance(client)
    advance(client)
    advance(client)  # day 4: nothing new
    assert sum(msg["text"] == DAY3_KN for msg in chat(client, token)) == 1
    with db_of(client).session() as s:
        due = s.scalars(
            select(m.Event).where(
                m.Event.type == REMINDER_DUE, m.Event.discharge_id == uuid.UUID(discharge_id)
            )
        ).all()
        assert sum(e.payload["day"] == 3 for e in due) == 1


def test_today_says_upcoming_before_the_time(client: TestClient, ramesh: tuple[str, str]) -> None:
    discharge_id, token = ramesh
    with db_of(client).session() as s:
        d = s.get(m.Discharge, uuid.UUID(discharge_id))
        assert d is not None
        d.discharged_on = d.discharged_on - timedelta(days=2)  # day 3, without sending
    today = client.get(f"/api/v1/patient/{token}/reminders/today").json()
    assert today["reminders"][0]["state"] == "upcoming"


def test_the_background_tick_sends_what_is_due(client: TestClient, ramesh: tuple[str, str]) -> None:
    discharge_id, token = ramesh
    app = client.app
    with db_of(client).session() as s:
        far = datetime.now(UTC) + timedelta(days=30)
        sent = asyncio.run(
            service.fire_due(s, app.state.bus, app.state.channels, far)  # type: ignore[attr-defined]
        )
    jobs = client.get(f"/api/v1/reminders/discharges/{discharge_id}").json()
    assert {r["status"] for r in jobs} == {"done"}
    assert sent >= len(jobs) >= 2  # Ramesh's days 3 and 6, plus the seeded patients'
    kinds = [msg["kind"] for msg in chat(client, token)]
    assert kinds.count("reminder") == len(jobs)


def test_closing_the_episode_cancels_its_reminders(
    client: TestClient, ramesh: tuple[str, str]
) -> None:
    discharge_id, _ = ramesh
    client.post(f"/api/v1/discharges/{discharge_id}/close")
    statuses = {
        r["status"] for r in client.get(f"/api/v1/reminders/discharges/{discharge_id}").json()
    }
    assert statuses == {"cancelled"}
    body = advance(client)
    assert "Ramesh" not in [p["patient_name"] for p in body["patients"]]


def test_seeded_patients_get_reminders_too(client: TestClient) -> None:
    sunita = str(seed_id("discharge:sunita"))
    pending = client.get(f"/api/v1/reminders/discharges/{sunita}").json()
    assert [r["day"] for r in pending] == [6]  # Sunita is on day 5
    body = advance(client)
    assert row(body, "Sunita") == {"patient_name": "Sunita", "recovery_day": 6, "reminders_sent": 1}
    token = tokens(client, sunita)["patient"]
    assert chat(client, token)[-1]["text"] == "कल आपके टांकों की जाँच है। कृपया अस्पताल आएँ।"


def test_reset_restores_the_schedule(client: TestClient) -> None:
    advance(client)
    assert client.post("/api/v1/demo/reset").status_code == 200
    sunita = str(seed_id("discharge:sunita"))
    assert [r["status"] for r in client.get(f"/api/v1/reminders/discharges/{sunita}").json()] == [
        "pending"
    ]
