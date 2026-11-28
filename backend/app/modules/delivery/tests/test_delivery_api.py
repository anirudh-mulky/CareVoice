import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app.channels.in_app import InAppChannel
from app.core import models as m
from app.core.db import Database
from app.core.events import MESSAGE_SENT, DomainEvent
from app.modules.demo.service import seed_id

RAMESH = (
    "Ramesh, 68, cataract right eye, standard template, "
    "diabetic so check sugar daily, language Kannada."
)


def db_of(client: TestClient) -> Database:
    database: Database = client.app.state.db  # type: ignore[attr-defined]
    return database


def approve(client: TestClient, transcript: str = RAMESH) -> str:
    card = client.post("/api/v1/discharges/extract", json={"transcript": transcript}).json()["card"]
    draft = client.post("/api/v1/discharges", json=card).json()
    res = client.post(f"/api/v1/discharges/{draft['id']}/approve")
    assert res.status_code == 200, res.text
    discharge_id: str = draft["id"]
    return discharge_id


def links(client: TestClient, discharge_id: str) -> dict[str, str]:
    res = client.post(f"/api/v1/delivery/discharges/{discharge_id}/links")
    assert res.status_code == 200, res.text
    return {link["recipient_type"]: link["url"].removeprefix("/p/") for link in res.json()}


def home(client: TestClient, token: str) -> dict[str, Any]:
    res = client.get(f"/api/v1/patient/{token}")
    assert res.status_code == 200, res.text
    body: dict[str, Any] = res.json()
    return body


def test_approve_posts_the_kannada_card_to_the_chat(client: TestClient) -> None:
    discharge_id = approve(client)
    token = links(client, discharge_id)["patient"]
    messages = client.get(f"/api/v1/patient/{token}/messages").json()
    # The care card comes first (teach-back then asks its question).
    assert messages[0]["kind"] == "instructions"
    note = messages[0]
    assert note["language"] == "kn"
    assert note["direction"] == "to_patient"
    # Spoken in Kannada, greeting first, then the red flags before anything else.
    assert note["text"].startswith("Ramesh, ನಿಮ್ಮ ಕಣ್ಣಿನ ಪೊರೆ ಶಸ್ತ್ರಚಿಕಿತ್ಸೆ")
    red_flags_at = note["text"].index("ಇವುಗಳಲ್ಲಿ ಯಾವುದಾದರೂ ಆದರೆ ಇಂದೇ ಆಸ್ಪತ್ರೆಗೆ ಬನ್ನಿ")
    assert red_flags_at < note["text"].index("ನಿಮ್ಮ ಔಷಧಿಗಳು")
    assert note["text_en"].startswith("Ramesh, here is your care card")


def test_patient_home_shows_the_card_in_kannada_red_flags_first(client: TestClient) -> None:
    token = links(client, approve(client))["patient"]
    body = home(client, token)
    card = body["card"]
    assert body["language"] == "kn" and card["translated"] is True
    assert body["viewer"] == {"type": "patient", "name": "Ramesh"}
    assert body["hospital"]["phone"] == "+91 90000 00000"
    assert body["recovery_day"] == 1
    assert card["title"] == "ಕಣ್ಣಿನ ಪೊರೆ ಶಸ್ತ್ರಚಿಕಿತ್ಸೆ"
    assert card["red_flags"][0] == "ದೃಷ್ಟಿ ಇದ್ದಕ್ಕಿದ್ದಂತೆ ಕಡಿಮೆಯಾದರೆ ಅಥವಾ ಕಾಣಿಸದಿದ್ದರೆ"
    assert len(card["red_flags"]) == 6
    assert card["medicines"][0]["instructions"] == "ದಿನಕ್ಕೆ 4 ಬಾರಿ, 1 ಹನಿ, 7 ದಿನ"
    assert card["labels"]["medicines"] == "ನಿಮ್ಮ ಔಷಧಿಗಳು"
    assert card["follow_up"] == "7ನೇ ದಿನ ತಪಾಸಣೆಗೆ ಬನ್ನಿ"
    # The doctor's extra has no verified translation: kept in English and marked.
    assert card["extras"] == [{"text": "Diabetic so check sugar daily", "translated": False}]


def test_carer_link_shows_the_same_card_and_chat(client: TestClient) -> None:
    tokens = links(client, approve(client))
    patient, carer = home(client, tokens["patient"]), home(client, tokens["carer"])
    assert carer["viewer"] == {"type": "carer", "name": "Kiran"}
    assert carer["card"] == patient["card"]
    assert (
        client.get(f"/api/v1/patient/{tokens['carer']}/messages").json()
        == client.get(f"/api/v1/patient/{tokens['patient']}/messages").json()
    )


def test_delivery_sends_to_patient_and_carer_and_issues_their_links(client: TestClient) -> None:
    channel: InAppChannel = client.app.state.channels.channels["in_app"]  # type: ignore[attr-defined]
    channel.delivered.clear()
    sent: list[DomainEvent] = []
    client.app.state.bus.subscribe(MESSAGE_SENT, lambda e, _s: sent.append(e))  # type: ignore[attr-defined]
    discharge_id = approve(client)
    assert [d.recipient_type.value for d in channel.delivered] == ["patient", "carer"]
    assert all("/p/" in d.text for d in channel.delivered)
    card = next(e for e in sent if e.payload["kind"] == "instructions")
    assert [d["state"] for d in card.payload["deliveries"]] == ["sent", "sent"]
    with db_of(client).session() as s:
        n = s.scalar(
            select(func.count())
            .select_from(m.AccessToken)
            .where(m.AccessToken.discharge_id == uuid.UUID(discharge_id))
        )
    assert n == 2


def test_tokens_are_long_random_and_stored_hashed(client: TestClient) -> None:
    discharge_id = approve(client)
    token = links(client, discharge_id)["patient"]
    assert len(token) >= 22  # 128 bits, URL-safe
    with db_of(client).session() as s:
        hashes = s.scalars(select(m.AccessToken.token_hash)).all()
    assert token not in hashes and all(len(h) == 64 for h in hashes)


def test_bad_expired_and_revoked_links_are_refused(client: TestClient) -> None:
    for bad in ("nope", "x" * 30):
        res = client.get(f"/api/v1/patient/{bad}")
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "link_invalid"

    discharge_id = approve(client)
    token = links(client, discharge_id)["patient"]
    with db_of(client).session() as s:
        s.execute(
            update(m.AccessToken)
            .where(m.AccessToken.discharge_id == uuid.UUID(discharge_id))
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
    assert client.get(f"/api/v1/patient/{token}").status_code == 404

    token = links(client, discharge_id)["patient"]
    from app.core.patient_access import revoke_tokens

    with db_of(client).session() as s:
        revoke_tokens(s, uuid.UUID(discharge_id))
    assert client.get(f"/api/v1/patient/{token}").status_code == 404


def test_links_expire_after_the_care_episode(client: TestClient) -> None:
    discharge_id = approve(client)
    links(client, discharge_id)
    with db_of(client).session() as s:
        expires = s.scalars(select(m.AccessToken.expires_at)).first()
    assert expires is not None
    days = (expires.date() - datetime.now(UTC).date()).days
    assert days == 7 + 30  # follow-up day + 30


def test_played_is_recorded_once_per_message(client: TestClient) -> None:
    token = links(client, approve(client))["patient"]
    note = client.get(f"/api/v1/patient/{token}/messages").json()[0]
    assert note["played_at"] is None
    assert client.post(f"/api/v1/patient/{token}/messages/{note['id']}/played").status_code == 204
    first = client.get(f"/api/v1/patient/{token}/messages").json()[0]["played_at"]
    client.post(f"/api/v1/patient/{token}/messages/{note['id']}/played")
    assert client.get(f"/api/v1/patient/{token}/messages").json()[0]["played_at"] == first


def test_a_link_cannot_touch_another_patients_messages(client: TestClient) -> None:
    ramesh = links(client, approve(client))["patient"]
    sunita_links = client.post(
        f"/api/v1/delivery/discharges/{seed_id('discharge:sunita')}/links"
    ).json()
    sunita = sunita_links[0]["url"].removeprefix("/p/")
    other = client.get(f"/api/v1/patient/{sunita}/messages").json()[0]["id"]
    assert client.post(f"/api/v1/patient/{ramesh}/messages/{other}/played").status_code == 404


def test_no_translation_falls_back_to_english_and_says_so(client: TestClient) -> None:
    # C-section has no Kannada translation in the seed.
    token = links(client, approve(client, "Kavya, 31, C-section, language Kannada"))["patient"]
    card = home(client, token)["card"]
    assert card["translated"] is False and card["language"] == "en"
    assert card["red_flags_title"] == "If any of these happen, come to the hospital today"


def test_draft_discharges_have_no_links(client: TestClient) -> None:
    card = client.post("/api/v1/discharges/extract", json={"transcript": RAMESH}).json()["card"]
    draft = client.post("/api/v1/discharges", json=card).json()
    res = client.post(f"/api/v1/delivery/discharges/{draft['id']}/links")
    assert res.status_code == 409


def test_demo_links_list_every_sent_patient(client: TestClient) -> None:
    approve(client)
    names = [d["patient_name"] for d in client.get("/api/v1/delivery/demo-links").json()]
    assert names == ["Murugan", "Ramesh", "Sunita"]


def test_seeded_patients_get_their_own_language(client: TestClient) -> None:
    demo = {d["patient_name"]: d for d in client.get("/api/v1/delivery/demo-links").json()}
    token = demo["Sunita"]["links"][0]["url"].removeprefix("/p/")
    body = home(client, token)
    assert body["language"] == "hi"
    assert body["card"]["red_flags_title"] == "इनमें से कुछ भी हो तो आज ही अस्पताल आएँ"
