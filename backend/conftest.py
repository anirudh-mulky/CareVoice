"""Shared fixtures for backend tests and module tests (app/modules/*/tests)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.db import Database
from app.core.events import EventBus
from app.main import create_app
from tests.support import make_settings


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(f"sqlite:///{tmp_path / 'unit.db'}")
    database.create_all()
    yield database
    database.engine.dispose()


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """A running app (lifespan executed, demo data seeded) on a temp database."""
    with TestClient(create_app(make_settings(tmp_path))) as test_client:
        yield test_client
