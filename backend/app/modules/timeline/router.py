import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import current_doctor
from app.core.db import get_session
from app.modules.timeline import service
from app.modules.timeline.schemas import Timeline

router = APIRouter(prefix="/api/v1/timeline", tags=["timeline"])


@router.get("/discharges/{discharge_id}", response_model=Timeline)
def discharge_timeline(
    discharge_id: uuid.UUID, session: Session = Depends(get_session)
) -> Timeline:
    """Every step of one care episode, with times, read-only."""
    return service.timeline(session, current_doctor(session).hospital_id, discharge_id)
