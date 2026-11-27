from pathlib import Path
from typing import Any

from app.core.config import Settings


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "database_url": f"sqlite:///{tmp_path / 'test.db'}",
        "static_dir": tmp_path / "static",
        "media_dir": tmp_path / "media",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)
