"""Discharges module: dictate, review and approve a discharge. Publishes discharge.approved."""

from fastapi import FastAPI

from app.core.events import EventBus
from app.modules.discharges.router import router


def register(app: FastAPI, bus: EventBus) -> None:
    app.include_router(router)
