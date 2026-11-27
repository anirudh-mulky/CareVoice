"""In-process event bus. Every published event is also written to the events table.

Modules publish domain events and subscribe to each other's, so no module imports
another module's service. Handlers run synchronously inside the publisher's session,
so the event row and every listener's writes commit (or roll back) together.
Production swaps in a Redis-backed bus with the same interface.
"""

import logging
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final

from sqlalchemy.orm import Session

from app.core.models import ActorType, Event, utcnow

logger = logging.getLogger("carevoice.events")

# Domain events (spec: "Modular design rules").
DISCHARGE_APPROVED: Final = "discharge.approved"
MESSAGE_SENT: Final = "message.sent"
TEACHBACK_SCORED: Final = "teachback.scored"
REPORT_CONFIRMED: Final = "report.confirmed"
REPORT_ALERT: Final = "report.alert"
REMEDY_APPROVED: Final = "remedy.approved"
DOCTOR_REPLIED: Final = "doctor.replied"
REMINDER_DUE: Final = "reminder.due"
DEMO_SEEDED: Final = "demo.seeded"
DEMO_RESET: Final = "demo.reset"

ALL: Final = "*"  # subscribe to every event (the timeline does this)


@dataclass(frozen=True)
class DomainEvent:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    hospital_id: uuid.UUID | None = None
    discharge_id: uuid.UUID | None = None
    actor_type: ActorType = ActorType.system
    actor_id: uuid.UUID | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=utcnow)


Handler = Callable[[DomainEvent, Session], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    def handlers_for(self, event_type: str) -> list[Handler]:
        return [*self._handlers.get(event_type, []), *self._handlers.get(ALL, [])]

    def publish(self, session: Session, event: DomainEvent) -> DomainEvent:
        """Write the event to the audit log, then deliver it to every subscriber.

        A handler that raises aborts the publisher's transaction, so a state change
        never commits without its event, and vice versa.
        """
        session.add(
            Event(
                id=event.id,
                hospital_id=event.hospital_id,
                discharge_id=event.discharge_id,
                actor_type=event.actor_type,
                actor_id=event.actor_id,
                type=event.type,
                payload=event.payload,
                created_at=event.created_at,
            )
        )
        session.flush()
        for handler in self.handlers_for(event.type):
            logger.debug("event %s -> %s", event.type, getattr(handler, "__qualname__", handler))
            handler(event, session)
        return event
