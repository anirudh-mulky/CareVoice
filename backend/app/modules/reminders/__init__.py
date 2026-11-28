"""Reminders module: schedules the template's reminders on discharge.approved and sends
them when due (a background tick, or the demo's "Simulate next day")."""

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.events import (
    DEMO_DAY_ADVANCED,
    DEMO_RESET,
    DEMO_SEEDED,
    DISCHARGE_APPROVED,
    EPISODE_CLOSED,
    DomainEvent,
    EventBus,
)
from app.core.modules import in_background
from app.core.sync import run_sync
from app.modules.reminders import service
from app.modules.reminders.router import patient_router, staff_router


def register(app: FastAPI, bus: EventBus) -> None:
    settings: Settings = app.state.settings

    def on_approved(event: DomainEvent, session: Session) -> None:
        assert event.discharge_id is not None
        service.schedule(session, bus, settings, event.discharge_id)

    def on_demo_data(_event: DomainEvent, session: Session) -> None:
        service.schedule_missing(session, bus, settings)

    def on_day_advanced(event: DomainEvent, session: Session) -> None:
        assert event.discharge_id is not None
        run_sync(
            service.advance_day(session, bus, app.state.channels, settings, event.discharge_id)
        )

    def on_closed(event: DomainEvent, session: Session) -> None:
        assert event.discharge_id is not None
        service.cancel(session, event.discharge_id)

    bus.subscribe(DISCHARGE_APPROVED, on_approved)
    bus.subscribe(DEMO_SEEDED, on_demo_data)
    bus.subscribe(DEMO_RESET, on_demo_data)
    bus.subscribe(DEMO_DAY_ADVANCED, on_day_advanced)
    bus.subscribe(EPISODE_CLOSED, on_closed)
    if settings.reminder_tick_seconds > 0:
        in_background(
            app,
            lambda: service.tick_forever(app.state.db, bus, app.state.channels, settings),
        )
    app.include_router(patient_router)
    app.include_router(staff_router)
