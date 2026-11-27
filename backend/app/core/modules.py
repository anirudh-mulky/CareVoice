"""Feature module loader.

Each feature lives in app/modules/<name>/ and exposes register(app, bus). main.py
calls load_modules() with ENABLED_MODULES; removing a name turns that feature off.
Modules not built yet are skipped with a log line, never a crash.
"""

import importlib
import logging
from collections.abc import Callable
from typing import Protocol, cast

from fastapi import FastAPI

from app.core.db import Database
from app.core.events import EventBus

logger = logging.getLogger("carevoice.modules")

StartupHook = Callable[[Database, EventBus], object]


class FeatureModule(Protocol):
    def register(self, app: FastAPI, bus: EventBus) -> None: ...


def on_startup(app: FastAPI, hook: StartupHook) -> None:
    """Run hook(db, bus) once tables exist, during app startup (e.g. seeding)."""
    app.state.startup_hooks.append(hook)


def load_modules(app: FastAPI, bus: EventBus, names: list[str]) -> list[str]:
    """Import and register each enabled module. Returns the names that loaded."""
    loaded: list[str] = []
    for name in names:
        try:
            module = importlib.import_module(f"app.modules.{name}")
        except ModuleNotFoundError as exc:
            if exc.name not in (f"app.modules.{name}", "app.modules"):
                raise  # a real import error inside the module: surface it
            logger.info("module %s is not built yet, skipping", name)
            continue
        if not hasattr(module, "register"):
            logger.warning("module %s has no register(app, bus), skipping", name)
            continue
        cast(FeatureModule, module).register(app, bus)
        loaded.append(name)
    app.state.modules = loaded
    return loaded
