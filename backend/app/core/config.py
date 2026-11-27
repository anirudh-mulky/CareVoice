"""Application settings.

Every value has a safe default so the app starts with no .env file and no keys.
A missing key never crashes the app: the provider registry falls back to demo mode.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ locally, /app inside the Docker image.
BACKEND_DIR = Path(__file__).resolve().parents[2]

ALL_MODULES = (
    "templates",
    "discharges",
    "delivery",
    "teachback",
    "reports",
    "outcomes",
    "reminders",
    "timeline",
    "demo",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CareVoice"
    version: str = "0.1.0"
    port: int = 3000

    # demo = no keys; real = use the providers below (falls back to demo per missing key)
    provider_mode: Literal["demo", "real"] = "demo"

    # Storage. In Docker the default resolves to sqlite:////app/data/carevoice.db.
    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'carevoice.db'}"
    media_dir: Path = BACKEND_DIR / "media"
    s3_bucket: str = ""
    static_dir: Path = BACKEND_DIR / "static"

    # Providers (Part 2 wires these into the registry)
    stt_provider: str = "browser"
    tts_provider: str = "browser"
    translate_provider: str = "browser"
    sarvam_api_key: SecretStr = SecretStr("")
    bhashini_api_key: SecretStr = SecretStr("")
    llm_provider: str = ""
    llm_model: str = ""
    llm_api_key: SecretStr = SecretStr("")

    frontend_origin: str = "http://localhost:5173"
    demo_endpoints: bool = True
    seed_on_startup: bool = True

    # "all" or a comma-separated list, e.g. "templates,discharges,demo".
    enabled_modules: str = "all"

    # Clinical tuning lives in config so doctors can adjust it without code changes.
    teachback_pass_threshold: float = 0.75
    teachback_max_tries: int = 2
    stt_confidence_alert_threshold: float = 0.6

    @property
    def module_names(self) -> list[str]:
        raw = self.enabled_modules.strip()
        if raw.lower() == "all":
            return list(ALL_MODULES)
        return [name.strip() for name in raw.split(",") if name.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
