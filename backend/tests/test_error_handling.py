"""Each row of the spec's error-handling table that the server handles, triggered on purpose."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app
from tests.support import make_settings

RAMESH = (
    "Ramesh, 68, cataract right eye, standard template, "
    "diabetic so check sugar daily, language Kannada."
)


def start(client: TestClient) -> tuple[str, dict[str, str]]:
    card = client.post("/api/v1/discharges/extract", json={"transcript": RAMESH}).json()["card"]
    discharge_id: str = client.post("/api/v1/discharges", json=card).json()["id"]
    client.post(f"/api/v1/discharges/{discharge_id}/approve")
    links = client.post(f"/api/v1/delivery/discharges/{discharge_id}/links").json()
    tokens = {x["recipient_type"]: x["url"].removeprefix("/p/") for x in links}
    return discharge_id, tokens


def report(client: TestClient, token: str, **body: Any) -> dict[str, Any]:
    res = client.post(f"/api/v1/patient/{token}/reports", json=body)
    assert res.status_code == 201, res.text
    out: dict[str, Any] = res.json()
    return out


def confirm_and_read(client: TestClient, token: str, report_id: str) -> dict[str, Any]:
    client.post(f"/api/v1/patient/{token}/reports/{report_id}/confirm", json={"answer": True})
    detail: dict[str, Any] = client.get(f"/api/v1/reports/{report_id}").json()
    return detail


@pytest.fixture
def failing(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(make_settings(tmp_path, simulate_failures="llm,translate"))
    with TestClient(app) as client:
        yield client


# --- Two failed attempts: tap symptom icons ------------------------------------------------


def test_tapped_icons_make_a_report_read_back_in_kannada(client: TestClient) -> None:
    _, tokens = start(client)
    out = report(client, tokens["patient"], icons=["redness", "pain"])
    assert out["read_back"] == "ನೀವು ಹೇಳಿದ್ದು: ಕೆಂಪು ಮತ್ತು ನೋವು. ಇದು ಸರಿಯೇ?"
    detail = confirm_and_read(client, tokens["patient"], out["report_id"])
    assert detail["type"] == "alert"  # redness is a red flag: escalated as usual
    assert detail["transcript_native"] == "ಕೆಂಪು ಮತ್ತು ನೋವು"
    assert detail["translation_en"] == "redness, pain"


def test_every_icon_is_understood(client: TestClient) -> None:
    _, tokens = start(client)
    icons = ["pain", "redness", "bleeding", "fever", "swelling", "vision_loss", "wound_problem"]
    out = report(client, tokens["patient"], icons=icons)
    detail = confirm_and_read(client, tokens["patient"], out["report_id"])
    assert len(detail["symptoms"]) == len(icons)


def test_unknown_icons_or_nothing_at_all_are_rejected(client: TestClient) -> None:
    _, tokens = start(client)
    url = f"/api/v1/patient/{tokens['patient']}/reports"
    assert client.post(url, json={"icons": ["headache"]}).status_code == 422
    assert client.post(url, json={"transcript": "  "}).status_code == 422


# --- Wrong language -------------------------------------------------------------------------


def test_speaking_another_language_reads_back_in_it_and_offers_to_switch(
    client: TestClient,
) -> None:
    _, tokens = start(client)
    out = report(client, tokens["patient"], transcript="आँख बहुत लाल है और दर्द है")
    assert out["language"] == "hi" and out["suggested_language"] == "hi"
    assert out["read_back"].startswith("आपने बताया")
    same = report(client, tokens["patient"], transcript="Kannu tumba kempagide")
    assert same["language"] == "kn" and same["suggested_language"] is None


def test_the_patient_can_tap_or_say_their_language(client: TestClient) -> None:
    _, tokens = start(client)
    url = f"/api/v1/patient/{tokens['patient']}/language"
    assert client.put(url, json={"language": "ta"}).json() == {"language": "ta"}
    home = client.get(f"/api/v1/patient/{tokens['patient']}").json()
    assert home["language"] == "ta" and home["card"]["title"] == "கண்புரை அறுவை சிகிச்சை"
    assert client.put(url, json={"spoken": "ಕನ್ನಡ"}).json() == {"language": "kn"}
    assert client.put(url, json={"spoken": "I want Hindi please"}).json() == {"language": "hi"}
    # No verified Hindi cataract card yet: the card is English, clearly marked, while the
    # buttons and voice follow the patient's choice.
    home = client.get(f"/api/v1/patient/{tokens['patient']}").json()
    assert home["card"]["translated"] is False
    assert (home["language"], home["ui_language"]) == ("en", "hi")
    bad = client.put(url, json={"spoken": "Klingon"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "unknown_language"


def test_a_carer_changing_language_only_changes_their_own_view(client: TestClient) -> None:
    discharge_id, tokens = start(client)
    client.put(f"/api/v1/patient/{tokens['carer']}/language", json={"language": "en"})
    assert client.get(f"/api/v1/patient/{tokens['carer']}").json()["language"] == "en"
    assert client.get(f"/api/v1/patient/{tokens['patient']}").json()["language"] == "kn"
    titles = [
        e["title"]
        for e in client.get(f"/api/v1/timeline/discharges/{discharge_id}").json()["entries"]
    ]
    assert "Carer changed language on screen: kn to en" in titles


# --- Low confidence escalates ---------------------------------------------------------------


def test_hard_to_hear_speech_goes_to_the_doctor_as_an_alert(client: TestClient) -> None:
    _, tokens = start(client)
    out = report(client, tokens["patient"], transcript="kannu turike ide", stt_confidence=0.4)
    detail = confirm_and_read(client, tokens["patient"], out["report_id"])
    assert detail["type"] == "alert" and "low_stt_confidence" in detail["reasons"]


# --- Providers failing ----------------------------------------------------------------------


def test_a_failing_llm_falls_back_to_rules_and_is_marked_needs_review(
    failing: TestClient,
) -> None:
    _, tokens = start(failing)
    out = report(failing, tokens["patient"], transcript="Kannu tumba kempagide, novu ide.")
    assert out["read_back"] == "ನೀವು ಹೇಳಿದ್ದು: ತುಂಬಾ ಕೆಂಪು ಮತ್ತು ನೋವು. ಇದು ಸರಿಯೇ?"
    detail = confirm_and_read(failing, tokens["patient"], out["report_id"])
    assert detail["type"] == "alert"
    assert detail["needs_review"] is True


def test_a_failing_translator_falls_back_to_the_phrasebook(failing: TestClient) -> None:
    _, tokens = start(failing)
    out = report(failing, tokens["patient"], transcript="naale check-up ge barabeka?")
    detail = confirm_and_read(failing, tokens["patient"], out["report_id"])
    text = "Please come to the hospital today."
    preview = failing.post(f"/api/v1/reports/{detail['id']}/reply/preview", json={"text": text})
    assert preview.json()["translated"] is True  # the phrasebook still knows it
    odd = failing.post(f"/api/v1/reports/{detail['id']}/reply/preview", json={"text": "Hm."})
    assert odd.json() == {"language": "kn", "text_native": "Hm.", "translated": False}


def test_simulated_failures_show_on_the_status_page(failing: TestClient) -> None:
    providers = {p["kind"]: p for p in failing.get("/api/v1/system/status").json()["providers"]}
    assert providers["llm"]["detail"].startswith("Simulated failure")


def test_real_mode_without_keys_reports_basic_voice_mode(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path, provider_mode="real", stt_provider="sarvam"))
    with TestClient(app) as client:
        stt = next(
            p for p in client.get("/api/v1/system/status").json()["providers"] if p["kind"] == "stt"
        )
    assert (stt["mode"], stt["status"]) == ("demo", "key_not_set")


# --- Friendly errors ------------------------------------------------------------------------


def test_an_unexpected_error_is_a_kind_message_without_details(tmp_path: Path) -> None:
    app: FastAPI = create_app(make_settings(tmp_path))

    def boom() -> None:
        raise RuntimeError("secret patient data in a stack trace")

    app.add_api_route("/api/v1/boom", boom)
    app.router.routes.insert(0, app.router.routes.pop())  # before the /api catch-all

    with TestClient(app, raise_server_exceptions=False) as client:
        res = client.get("/api/v1/boom")
    assert res.status_code == 500
    assert res.json() == {
        "error": {
            "code": "internal_error",
            "message": "Something went wrong on our side. Please try again.",
            "details": None,
        }
    }
    assert "secret" not in res.text
