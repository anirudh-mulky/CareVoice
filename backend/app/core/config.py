"""Application settings.

Every value has a safe default so the app starts with no .env file and no keys.
Part 1 extends this with database, media and provider settings.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CareVoice"
    version: str = "0.1.0"
    provider_mode: Literal["demo", "real"] = "demo"
    port: int = 3000
    # Built React app. In Docker it sits at /app/static; locally run `npm run build`.
    static_dir: Path = BACKEND_DIR / "static"
    frontend_origin: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
