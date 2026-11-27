from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def make_client(static_dir: Path) -> TestClient:
    return TestClient(create_app(Settings(static_dir=static_dir)))


def test_health_reports_demo_mode_by_default(tmp_path: Path) -> None:
    res = make_client(tmp_path).get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["mode"] == "demo"


def test_unknown_api_path_is_404_not_the_spa(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<div id=root></div>")
    res = make_client(tmp_path).get("/api/v1/nope")
    assert res.status_code == 404


def test_root_and_client_routes_serve_index(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<title>CareVoice</title>")
    client = make_client(tmp_path)
    for path in ("/", "/doctor", "/patient/abc"):
        res = client.get(path)
        assert res.status_code == 200
        assert "CareVoice" in res.text


def test_static_files_are_served(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("index")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    res = make_client(tmp_path).get("/favicon.svg")
    assert res.text == "<svg/>"


def test_path_traversal_falls_back_to_index(tmp_path: Path) -> None:
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("index")
    (tmp_path / "secret.txt").write_text("secret")
    res = make_client(static).get("/..%2Fsecret.txt")
    assert "secret" not in res.text


def test_missing_build_shows_fallback_page_not_json(tmp_path: Path) -> None:
    res = make_client(tmp_path / "missing").get("/")
    assert res.status_code == 200
    assert "CareVoice" in res.text
    assert res.headers["content-type"].startswith("text/html")
