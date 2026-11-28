"""Demo module: seeds synthetic data on first start; POST /api/v1/demo/reset and
/api/v1/demo/advance-day ("Simulate next day")."""

from fastapi import FastAPI

from app.core.config import Settings
from app.core.events import EventBus
from app.core.modules import on_startup
from app.modules.demo import service
from app.modules.demo.router import router


def register(app: FastAPI, bus: EventBus) -> None:
    settings: Settings = app.state.settings
    if settings.seed_on_startup:
        on_startup(app, service.seed_if_empty)
    if settings.demo_endpoints:
        app.include_router(router)
