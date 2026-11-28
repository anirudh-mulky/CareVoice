"""Voice module: server-side speech for real mode. POST /api/v1/voice/transcribe turns a
recording into text; POST /api/v1/patient/{token}/speak returns cached MP3 audio."""

from fastapi import FastAPI

from app.core.events import EventBus
from app.modules.voice.router import patient_router, router


def register(app: FastAPI, bus: EventBus) -> None:
    app.include_router(router)
    app.include_router(patient_router)
