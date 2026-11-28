"""Delivery module: listens to discharge.approved, posts the care card and sends it to the
patient and carers; serves the patient's home and chat through their link."""

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.events import DISCHARGE_APPROVED, DomainEvent, EventBus
from app.modules.delivery import service
from app.modules.delivery.router import demo_router, patient_router, staff_router


def register(app: FastAPI, bus: EventBus) -> None:
    def on_discharge_approved(event: DomainEvent, session: Session) -> None:
        assert event.discharge_id is not None
        service.deliver(session, bus, app.state.providers, app.state.channels, event.discharge_id)

    bus.subscribe(DISCHARGE_APPROVED, on_discharge_approved)
    app.include_router(patient_router)
    app.include_router(staff_router)
    settings: Settings = app.state.settings
    if settings.demo_endpoints:
        app.include_router(demo_router)
