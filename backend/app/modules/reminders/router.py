import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import current_doctor
from app.core.db import get_session
from app.core.patient_access import resolve_token
from app.modules.reminders import service
from app.modules.reminders.schemas import ScheduledReminder, TodayReminders

patient_router = APIRouter(prefix="/api/v1/patient", tags=["patient"])
staff_router = APIRouter(prefix="/api/v1/reminders", tags=["reminders"])


@patient_router.get("/{token}/reminders/today", response_model=TodayReminders)
def today(token: str, session: Session = Depends(get_session)) -> TodayReminders:
    """Today's reminders for the patient home, in the patient's language."""
    return service.today(session, resolve_token(session, token))


@staff_router.get("/discharges/{discharge_id}", response_model=list[ScheduledReminder])
def scheduled(
    discharge_id: uuid.UUID, session: Session = Depends(get_session)
) -> list[ScheduledReminder]:
    """Every reminder for one care episode: sent, upcoming or cancelled."""
    return service.scheduled(session, current_doctor(session).hospital_id, discharge_id)
