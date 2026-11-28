"""Reports module: the patient's spoken symptom -> read-back -> yes/no -> English report on
the doctor's dashboard. Publishes report.confirmed (and report.rejected, report.seen)."""

from fastapi import FastAPI

from app.core.events import EventBus
from app.modules.reports.router import patient_router, staff_router


def register(app: FastAPI, bus: EventBus) -> None:
    app.include_router(patient_router)
    app.include_router(staff_router)
