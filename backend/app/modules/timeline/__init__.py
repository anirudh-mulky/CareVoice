"""Timeline module: listens to every event and serves a read-only, time-stamped record of
each care episode for the doctor's patient page."""

from fastapi import FastAPI

from app.core.events import ALL, EventBus
from app.modules.timeline import service
from app.modules.timeline.router import router


def register(app: FastAPI, bus: EventBus) -> None:
    bus.subscribe(ALL, service.notice)
    app.include_router(router)
