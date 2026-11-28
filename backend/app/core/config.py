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
    "voice",
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
    media_dir: Path = BACKEND_DIR / "data" / "media"  # report audio; on the Docker volume
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
    # Real providers (Part 12). Keys come only from the environment, never from the repo.
    sarvam_stt_model: str = "saaras:v4"
    sarvam_tts_model: str = "bulbul:v3"
    sarvam_tts_speaker: str = "shubh"  # must be a bulbul:v3 speaker
    sarvam_translate_model: str = "mayura:v1"
    provider_timeout_seconds: float = 20.0

    frontend_origin: str = "http://localhost:5173"
    demo_endpoints: bool = True
    seed_on_startup: bool = True

    # "all" or a comma-separated list, e.g. "templates,discharges,demo".
    enabled_modules: str = "all"
    # Delivery channels, comma-separated: in_app now; whatsapp, sms, ivr later.
    enabled_channels: str = "in_app"

    # Clinical tuning lives in config so doctors can adjust it without code changes.
    teachback_pass_threshold: float = 0.75
    teachback_max_tries: int = 2
    stt_confidence_alert_threshold: float = 0.6
    report_audio_max_bytes: int = 2_000_000  # 60 s of opus is ~0.5 MB
    # Reminders: template times are hospital-local (India: UTC+5:30, no daylight saving).
    hospital_utc_offset_minutes: int = 330
    reminder_tick_seconds: int = 60  # how often due reminders are sent; 0 turns the loop off
    # Demo/QA only: make providers fail on purpose ("llm", "translate") to show the fallbacks.
    simulate_failures: str = ""

    @property
    def module_names(self) -> list[str]:
        raw = self.enabled_modules.strip()
        if raw.lower() == "all":
            return list(ALL_MODULES)
        return [name.strip() for name in raw.split(",") if name.strip()]

    @property
    def channel_names(self) -> list[str]:
        return [n.strip().lower() for n in self.enabled_channels.split(",") if n.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
