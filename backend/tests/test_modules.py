from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.events import EventBus
from app.core.modules import load_modules
from app.main import create_app
from tests.support import make_settings


def test_unbuilt_modules_are_skipped_not_fatal() -> None:
    app = FastAPI()
    app.state.settings = make_settings(Path("/tmp"))
    app.state.startup_hooks = []
    loaded = load_modules(app, EventBus(), ["templates", "does_not_exist", "demo"])
    assert loaded == ["demo"]
    assert app.state.modules == ["demo"]


def test_default_config_loads_demo_module(client: TestClient) -> None:
    assert "demo" in client.app.state.modules  # type: ignore[attr-defined]


def test_removing_a_module_from_the_list_turns_it_off(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path, enabled_modules="templates"))
    with TestClient(app) as client:
        assert client.app.state.modules == []  # type: ignore[attr-defined]
        assert client.post("/api/v1/demo/reset").status_code == 404
