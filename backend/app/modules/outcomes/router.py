import uuid

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.context import current_doctor
from app.core.db import get_session
from app.modules.outcomes import service
from app.modules.outcomes.schemas import (
    ActionResult,
    RemedyApproval,
    ReplyIn,
    ReplyPreview,
    ReportActions,
)

# Doctor actions on a confirmed report, and on the care episode.
router = APIRouter(prefix="/api/v1", tags=["outcomes"])


@router.get("/reports/{report_id}/actions", response_model=ReportActions)
def report_actions(report_id: uuid.UUID, session: Session = Depends(get_session)) -> ReportActions:
    """Template remedies (with the patient's wording), quick replies, and what was sent."""
    return service.actions(session, current_doctor(session).hospital_id, report_id)


@router.post("/reports/{report_id}/remedy", response_model=ActionResult)
async def approve_remedy(
    report_id: uuid.UUID,
    body: RemedyApproval,
    request: Request,
    session: Session = Depends(get_session),
) -> ActionResult:
    """Send the chosen template remedies, in the patient's language. Never for alerts."""
    staff = current_doctor(session)
    state = request.app.state
    return await service.approve_remedy(
        session, state.bus, state.channels, staff.hospital_id, staff.id, report_id, body.minor_ids
    )


@router.post("/reports/{report_id}/reply/preview", response_model=ReplyPreview)
async def preview_reply(
    report_id: uuid.UUID, body: ReplyIn, request: Request, session: Session = Depends(get_session)
) -> ReplyPreview:
    """What the patient would receive, and whether it could be translated."""
    staff = current_doctor(session)
    return await service.preview_reply(
        session, request.app.state.providers, staff.hospital_id, report_id, body.text
    )


@router.post("/reports/{report_id}/reply", response_model=ActionResult)
async def reply(
    report_id: uuid.UUID,
    body: ReplyIn,
    request: Request,
    idempotency_key: str | None = Header(default=None, max_length=100),
    session: Session = Depends(get_session),
) -> ActionResult:
    """The doctor's reply (typed or dictated), translated to the patient's language."""
    staff = current_doctor(session)
    state = request.app.state
    return await service.reply(
        session,
        state.bus,
        state.providers,
        state.channels,
        staff.hospital_id,
        staff.id,
        report_id,
        body.text,
        idempotency_key,
    )


@router.post("/discharges/{discharge_id}/alert/handled", response_model=ActionResult)
def alert_handled(
    discharge_id: uuid.UUID, request: Request, session: Session = Depends(get_session)
) -> ActionResult:
    """The doctor has dealt with the alert."""
    staff = current_doctor(session)
    return service.handle_alert(
        session, request.app.state.bus, staff.hospital_id, staff.id, discharge_id
    )


@router.post("/discharges/{discharge_id}/close", response_model=ActionResult)
def close_episode(
    discharge_id: uuid.UUID, request: Request, session: Session = Depends(get_session)
) -> ActionResult:
    """End the care episode; the patient's links stop working."""
    staff = current_doctor(session)
    return service.close_episode(
        session, request.app.state.bus, staff.hospital_id, staff.id, discharge_id
    )
