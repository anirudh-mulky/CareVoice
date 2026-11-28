"""Outcomes module: listens to report.confirmed. Alerts turn the dashboard red and send the
patient a safety message; minor reports get a template remedy after doctor approval; any
report can get a translated doctor reply. Also: alert handled, close the episode."""

import uuid

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.core.events import REPORT_CONFIRMED, DomainEvent, EventBus
from app.core.sync import run_sync
from app.modules.outcomes import service
from app.modules.outcomes.router import router


def register(app: FastAPI, bus: EventBus) -> None:
    service.install_quick_replies(app.state.providers)

    def on_report_confirmed(event: DomainEvent, session: Session) -> None:
        report_id = uuid.UUID(str(event.payload["report_id"]))
        run_sync(service.on_report_confirmed(session, bus, app.state.channels, report_id))

    bus.subscribe(REPORT_CONFIRMED, on_report_confirmed)
    app.include_router(router)
