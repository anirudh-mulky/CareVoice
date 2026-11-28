import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core import models as m
from app.core.db import Base, Database
from app.core.events import DISCHARGE_APPROVED, DomainEvent
from app.modules.demo.service import seed_id

RAMESH = (
    "Ramesh, 68, cataract right eye, standard template, "
    "diabetic so check sugar daily, language Kannada."
)
UNCLEAR = "Ramesh, 68, cataract right eye, language Kannada, add timolol drops"


def extract(client: TestClient, transcript: str) -> dict[str, Any]:
    res = client.post("/api/v1/discharges/extract", json={"transcript": transcript})
    assert res.status_code == 200, res.text
    body: dict[str, Any] = res.json()
    return body


def draft(client: TestClient, card: dict[str, Any]) -> dict[str, Any]:
    res = client.post("/api/v1/discharges", json=card)
    assert res.status_code == 201, res.text
    body: dict[str, Any] = res.json()
    return body


def count(db: Database, model: type[Base], *where: Any) -> int:
    with db.session() as s:
        return s.scalar(select(func.count()).select_from(model).where(*where)) or 0


def db_of(client: TestClient) -> Database:
    database: Database = client.app.state.db  # type: ignore[attr-defined]
    return database


# --- Extraction -------------------------------------------------------------------


def test_the_ramesh_sentence_fills_the_card(client: TestClient) -> None:
    body = extract(client, RAMESH)
    card = body["card"]
    assert card["patient_name"] == "Ramesh"
    assert card["age"] == 68
    assert card["template_name"] == "Cataract surgery"
    assert card["template_id"] == str(seed_id("template:cataract"))
    assert card["side"] == "right"
    assert card["language"] == "kn"
    assert card["extra_instructions"] == ["Diabetic so check sugar daily"]
    assert body["unclear_fields"] == []
    assert body["matched_patient"]["id"] == str(seed_id("patient:ramesh"))
    assert body["source"] == "rules"


def test_an_unclear_dose_is_flagged(client: TestClient) -> None:
    body = extract(client, UNCLEAR)
    assert body["unclear_fields"] == ["extra_instructions[0]"]
    assert body["card"]["extra_instructions"] == ["Add timolol drops"]


def test_extraction_saves_nothing(client: TestClient) -> None:
    before = count(db_of(client), m.Discharge)
    extract(client, RAMESH)
    assert count(db_of(client), m.Discharge) == before


def test_template_picker_lists_latest_templates(client: TestClient) -> None:
    names = {t["name"] for t in client.get("/api/v1/discharges/templates").json()}
    assert names == {"Cataract surgery", "C-section"}


# --- Drafts ---------------------------------------------------------------------------


def test_draft_reuses_the_existing_patient(client: TestClient) -> None:
    patients_before = count(db_of(client), m.Patient)
    out = draft(client, extract(client, RAMESH)["card"])
    assert out["status"] == "draft"
    assert out["patient"]["id"] == str(seed_id("patient:ramesh"))
    assert out["recovery_day"] == 1
    assert count(db_of(client), m.Patient) == patients_before


def test_draft_creates_a_new_patient_and_carer(client: TestClient) -> None:
    card = extract(
        client, "Lakshmi, 61, cataract left eye, language Tamil, daughter phone 98450 12345"
    )["card"]
    out = draft(client, card)
    assert out["patient"]["name"] == "Lakshmi"
    assert out["patient"]["preferred_language"] == "ta"
    assert out["card"]["carer_phone"] == "+919845012345"
    assert out["unclear_fields"] == []


def test_draft_needs_a_name_and_template(client: TestClient) -> None:
    res = client.post("/api/v1/discharges", json={"age": 40, "language": "kn"})
    assert res.status_code == 422
    error = res.json()["error"]
    assert error["code"] == "missing_required"
    assert "patient_name" in error["details"]["unclear_fields"]


def test_editing_the_card_recomputes_unclear_fields(client: TestClient) -> None:
    out = draft(client, extract(client, UNCLEAR)["card"])
    assert out["unclear_fields"] == ["extra_instructions[0]"]
    fixed = out["card"] | {"extra_instructions": ["Timolol 0.5% 1 drop twice daily"]}
    res = client.patch(f"/api/v1/discharges/{out['id']}", json=fixed)
    assert res.status_code == 200
    assert res.json()["unclear_fields"] == []


# --- Approval gate --------------------------------------------------------------------


def test_approve_is_blocked_while_fields_are_unclear(client: TestClient) -> None:
    out = draft(client, extract(client, UNCLEAR)["card"])
    res = client.post(f"/api/v1/discharges/{out['id']}/approve")
    assert res.status_code == 422
    error = res.json()["error"]
    assert error["code"] == "unclear_fields"
    assert error["details"]["unclear_fields"] == ["extra_instructions[0]"]
    # Nothing was sent and nothing was published.
    assert client.get(f"/api/v1/discharges/{out['id']}").json()["status"] == "draft"
    assert (
        count(
            db_of(client),
            m.Event,
            m.Event.type == DISCHARGE_APPROVED,
            m.Event.discharge_id == uuid.UUID(out["id"]),
        )
        == 0
    )


def test_a_missing_age_also_blocks(client: TestClient) -> None:
    out = draft(client, extract(client, "Kavya, cataract right eye, language Kannada")["card"])
    assert out["patient"]["age"] is None
    assert "age" in out["unclear_fields"]
    assert client.post(f"/api/v1/discharges/{out['id']}/approve").status_code == 422


def test_approve_sends_and_publishes_once(client: TestClient) -> None:
    received: list[DomainEvent] = []
    client.app.state.bus.subscribe(DISCHARGE_APPROVED, lambda e, _s: received.append(e))  # type: ignore[attr-defined]
    out = draft(client, extract(client, RAMESH)["card"])

    first = client.post(
        f"/api/v1/discharges/{out['id']}/approve", headers={"Idempotency-Key": "tap-1"}
    )
    assert first.status_code == 200
    assert first.json()["outcome"] == "approved"
    assert first.json()["discharge"]["status"] == "sent"
    assert first.json()["discharge"]["approved_at"] is not None

    payload = received[0].payload
    assert payload["patient_id"] == str(seed_id("patient:ramesh"))
    assert payload["language"] == "kn"
    assert payload["extra_instructions"] == ["Diabetic so check sugar daily"]
    assert payload["carer_ids"] == [str(seed_id("carer:ramesh-kiran"))]


def test_double_tap_on_approve_never_sends_twice(client: TestClient) -> None:
    received: list[DomainEvent] = []
    client.app.state.bus.subscribe(DISCHARGE_APPROVED, lambda e, _s: received.append(e))  # type: ignore[attr-defined]
    out = draft(client, extract(client, RAMESH)["card"])
    url = f"/api/v1/discharges/{out['id']}/approve"

    first = client.post(url, headers={"Idempotency-Key": "tap-1"}).json()
    second = client.post(url, headers={"Idempotency-Key": "tap-1"}).json()
    third = client.post(url).json()

    assert first["outcome"] == "approved"
    assert second["outcome"] == third["outcome"] == "already_approved"
    assert second["discharge"]["approved_at"] == first["discharge"]["approved_at"]
    assert len(received) == 1
    assert (
        count(
            db_of(client),
            m.Event,
            m.Event.type == DISCHARGE_APPROVED,
            m.Event.discharge_id == uuid.UUID(out["id"]),
        )
        == 1
    )


def test_a_sent_discharge_cannot_be_edited(client: TestClient) -> None:
    out = draft(client, extract(client, RAMESH)["card"])
    client.post(f"/api/v1/discharges/{out['id']}/approve")
    res = client.patch(f"/api/v1/discharges/{out['id']}", json=out["card"])
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "not_draft"


def test_unknown_discharge_is_404_in_the_error_shape(client: TestClient) -> None:
    res = client.post("/api/v1/discharges/00000000-0000-0000-0000-000000000000/approve")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"


# --- Dashboard list -------------------------------------------------------------------


def test_list_puts_alerts_first_and_filters_by_status(client: TestClient) -> None:
    items = client.get("/api/v1/discharges").json()
    assert items[0]["status"] == "alert"
    assert items[0]["patient_name"] == "Murugan"
    assert items[0]["recovery_day"] == 3
    understood = client.get("/api/v1/discharges", params={"status": "understood"}).json()
    assert [i["patient_name"] for i in understood] == ["Sunita"]
