from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from tests.support import make_settings


def test_status_lists_every_provider_in_demo_mode(client: TestClient) -> None:
    body = client.get("/api/v1/system/status").json()
    assert body["mode"] == "demo"
    assert body["key_not_set"] is False
    assert [p["kind"] for p in body["providers"]] == ["stt", "tts", "translate", "llm"]
    assert {p["mode"] for p in body["providers"]} == {"demo"}
    assert body["channels"] == [{"name": "in_app", "status": "enabled"}]
    assert "demo" in body["modules"]


def test_status_reports_key_not_set_without_crashing(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, provider_mode="real", llm_provider="openai")
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/health").json()["status"] == "ok"
        body = client.get("/api/v1/system/status").json()
    llm = next(p for p in body["providers"] if p["kind"] == "llm")
    assert body["key_not_set"] is True
    assert llm["status"] == "key_not_set"
    assert llm["mode"] == "demo"
    assert llm["detail"] == "Key not set, using demo mode"
