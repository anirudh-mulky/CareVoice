import pytest

from app.core.config import ALL_MODULES, Settings


def test_every_setting_has_a_default_with_no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("PROVIDER_MODE", "DATABASE_URL", "ENABLED_MODULES", "DEMO_ENDPOINTS"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)
    assert settings.provider_mode == "demo"
    assert settings.database_url.startswith("sqlite:///")
    assert settings.database_url.endswith("data/carevoice.db")
    assert settings.demo_endpoints is True
    assert settings.llm_api_key.get_secret_value() == ""
    assert settings.teachback_pass_threshold == 0.75
    assert settings.teachback_max_tries == 2
    assert settings.stt_confidence_alert_threshold == 0.6


def test_env_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROVIDER_MODE", "real")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db/carevoice")
    settings = Settings(_env_file=None)
    assert settings.provider_mode == "real"
    assert settings.database_url.startswith("postgresql")


def test_secrets_are_not_printed() -> None:
    settings = Settings(_env_file=None, llm_api_key="sk-test-123")
    assert "sk-test-123" not in repr(settings)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("all", list(ALL_MODULES)),
        ("ALL", list(ALL_MODULES)),
        ("demo", ["demo"]),
        (" templates, demo ,", ["templates", "demo"]),
        ("", []),
    ],
)
def test_enabled_modules_parsing(raw: str, expected: list[str]) -> None:
    assert Settings(_env_file=None, enabled_modules=raw).module_names == expected
