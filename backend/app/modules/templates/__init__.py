"""Templates module: list, view and version the doctor's care templates."""

from fastapi import FastAPI

from app.core.events import EventBus
from app.modules.templates.router import router


def register(app: FastAPI, bus: EventBus) -> None:
    app.include_router(router)
