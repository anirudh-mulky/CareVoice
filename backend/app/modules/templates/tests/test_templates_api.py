from typing import Any

from fastapi.testclient import TestClient

from app.modules.demo.service import seed_id

CATARACT = str(seed_id("template:cataract"))


def test_list_shows_latest_templates_with_counts_and_languages(client: TestClient) -> None:
    items = {t["name"]: t for t in client.get("/api/v1/templates").json()}
    assert set(items) == {"Cataract surgery", "C-section"}
    cataract = items["Cataract surgery"]
    assert (cataract["red_flags"], cataract["minor_symptoms"], cataract["medicines"]) == (6, 3, 3)
    assert cataract["languages"] == ["en", "kn", "ta"]
    assert items["C-section"]["languages"] == ["en", "hi"]


def test_view_returns_the_full_template_and_translations(client: TestClient) -> None:
    tpl = client.get(f"/api/v1/templates/{CATARACT}").json()
    assert tpl["version"] == 1 and tpl["versions"] == [1]
    assert tpl["red_flags"][0]["id"] == "rf_vision_loss"
    assert tpl["follow_up_day"] == 7
    assert tpl["translations"]["kn"]["name"] == "ಕಣ್ಣಿನ ಪೊರೆ ಶಸ್ತ್ರಚಿಕಿತ್ಸೆ"


def test_unknown_template_or_version_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/templates/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.get(f"/api/v1/templates/{CATARACT}", params={"version": 9}).status_code == 404


def test_saving_creates_a_new_version_and_keeps_the_old_one(client: TestClient) -> None:
    current: dict[str, Any] = client.get(f"/api/v1/templates/{CATARACT}").json()
    body = {
        k: current[k]
        for k in (
            "name",
            "condition",
            "medicines",
            "dos",
            "donts",
            "red_flags",
            "minor_symptoms",
            "reminders",
            "follow_up_day",
        )
    }
    body["dos"] = [*body["dos"], "Sleep on your back for 3 days"]
    res = client.post("/api/v1/templates", json=body | {"id": CATARACT})
    assert res.status_code == 201
    saved = res.json()
    assert saved["version"] == 2 and saved["versions"] == [1, 2]
    assert saved["languages"] == ["en"]  # the new version still needs translating
    old = client.get(f"/api/v1/templates/{CATARACT}", params={"version": 1}).json()
    assert "Sleep on your back for 3 days" not in old["dos"]
    listed = {t["name"]: t for t in client.get("/api/v1/templates").json()}
    assert listed["Cataract surgery"]["version"] == 2


def test_a_new_template_needs_red_flags(client: TestClient) -> None:
    res = client.post(
        "/api/v1/templates", json={"name": "Knee", "condition": "knee", "red_flags": []}
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "invalid_request"


def test_creating_a_template(client: TestClient) -> None:
    res = client.post(
        "/api/v1/templates",
        json={
            "name": "Knee replacement",
            "condition": "knee replacement",
            "red_flags": [{"id": "rf_fever", "label_en": "Fever"}],
        },
    )
    assert res.status_code == 201
    assert res.json()["version"] == 1


def test_extract_a_dictated_template_without_saving(client: TestClient) -> None:
    before = len(client.get("/api/v1/templates").json())
    res = client.post(
        "/api/v1/templates/extract",
        json={
            "transcript": "Template for knee replacement. Paracetamol 500 mg twice daily. "
            "Come back if fever or wound pus."
        },
    )
    assert res.status_code == 200
    draft = res.json()
    assert draft["template"]["name"] == "Knee replacement"
    assert [f["label_en"] for f in draft["template"]["red_flags"]] == ["Fever", "Wound pus"]
    assert draft["source"] == "rules"
    assert len(client.get("/api/v1/templates").json()) == before
