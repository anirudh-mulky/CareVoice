from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.context import current_doctor
from app.core.db import get_session
from app.modules.demo import service
from app.modules.demo.schemas import AdvancedPatient, AdvanceResult, ResetResult

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


@router.post("/reset", response_model=ResetResult)
def reset_demo(request: Request) -> ResetResult:
    """Restore the seeded demo data. Only available when DEMO_ENDPOINTS=true."""
    counts = service.reset(request.app.state.db, request.app.state.bus)
    return ResetResult(counts=counts)


@router.post("/advance-day", response_model=AdvanceResult)
def advance_day(request: Request, session: Session = Depends(get_session)) -> AdvanceResult:
    """Simulate next day: every running care episode moves one day on and that day's
    reminders are sent. Only available when DEMO_ENDPOINTS=true."""
    hospital_id = current_doctor(session).hospital_id
    rows = service.advance_day(session, request.app.state.bus, hospital_id)
    return AdvanceResult(
        patients=[AdvancedPatient(**r) for r in rows],
        reminders_sent=sum(r["reminders_sent"] for r in rows),
    )
