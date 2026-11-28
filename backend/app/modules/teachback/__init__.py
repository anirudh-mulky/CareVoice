"""Teach-back module: asks "when should you come back?" once the care card is sent, scores
spoken answers and publishes teachback.scored."""

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.core.events import MESSAGE_SENT, DomainEvent, EventBus
from app.core.models import MessageKind
from app.modules.teachback import service
from app.modules.teachback.router import router


def register(app: FastAPI, bus: EventBus) -> None:
    def on_message_sent(event: DomainEvent, session: Session) -> None:
        # Ask once, right after the care card itself is sent.
        if event.payload.get("kind") == MessageKind.instructions.value and event.discharge_id:
            service.ask_question(session, bus, event.discharge_id)

    bus.subscribe(MESSAGE_SENT, on_message_sent)
    app.include_router(router)
