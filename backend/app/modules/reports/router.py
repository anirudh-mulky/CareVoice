import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.core.context import current_doctor
from app.core.db import get_session
from app.core.errors import AppError
from app.core.models import ReportStatus, ReportType
from app.core.patient_access import resolve_token
from app.modules.reports import service
from app.modules.reports.schemas import (
    ConfirmIn,
    ConfirmOut,
    ReadBack,
    ReportDetail,
    ReportIn,
    ReportListItem,
    ReportUpdate,
)

# Patient and carer: no login, the link token is the key.
patient_router = APIRouter(prefix="/api/v1/patient", tags=["patient"])
# Doctor: confirmed reports only.
staff_router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@patient_router.post("/{token}/reports", response_model=ReadBack, status_code=201)
async def create_report(
    token: str, body: ReportIn, request: Request, session: Session = Depends(get_session)
) -> ReadBack:
    """What the patient said -> the read-back in their language (pending their yes/no)."""
    state = request.app.state
    return await service.create_report(
        session, state.bus, state.providers, state.settings, resolve_token(session, token), body
    )


@patient_router.post("/{token}/reports/{report_id}/confirm", response_model=ConfirmOut)
def confirm_report(
    token: str,
    report_id: uuid.UUID,
    body: ConfirmIn,
    request: Request,
    session: Session = Depends(get_session),
) -> ConfirmOut:
    """Yes sends the English report to the doctor; no asks the patient to say it again."""
    access = resolve_token(session, token)
    return service.confirm(session, request.app.state.bus, access, report_id, body)


@patient_router.put("/{token}/reports/{report_id}/audio", status_code=204)
async def upload_audio(
    token: str, report_id: uuid.UUID, request: Request, session: Session = Depends(get_session)
) -> Response:
    """The recording as the raw request body (Content-Type: audio/webm, max 2 MB)."""
    settings = request.app.state.settings
    declared = int(request.headers.get("content-length") or 0)
    if declared > settings.report_audio_max_bytes:
        raise AppError(413, "audio_too_large", "The recording is too long.")
    access = resolve_token(session, token)
    data = await request.body()
    content_type = request.headers.get("content-type", "")
    service.save_audio(session, settings, access, report_id, data, content_type)
    return Response(status_code=204)


@staff_router.get("", response_model=list[ReportListItem])
def list_reports(
    status: ReportStatus | None = Query(default=None),
    type: ReportType | None = Query(default=None),
    discharge_id: uuid.UUID | None = Query(default=None, description="One care episode"),
    session: Session = Depends(get_session),
) -> list[ReportListItem]:
    """Confirmed reports, alerts first, then unseen, then newest."""
    hospital_id = current_doctor(session).hospital_id
    return service.list_reports(session, hospital_id, status, type, discharge_id)


@staff_router.get("/{report_id}", response_model=ReportDetail)
def get_report(report_id: uuid.UUID, session: Session = Depends(get_session)) -> ReportDetail:
    """The English report beside the patient's own words, with recovery day and medicines."""
    return service.get_report(session, current_doctor(session).hospital_id, report_id)


@staff_router.patch("/{report_id}", response_model=ReportDetail)
def update_report(
    report_id: uuid.UUID,
    body: ReportUpdate,
    request: Request,
    session: Session = Depends(get_session),
) -> ReportDetail:
    """Mark a report seen. (Remedy approval arrives with the outcomes module.)"""
    staff = current_doctor(session)
    return service.mark_seen(session, request.app.state.bus, staff.hospital_id, staff.id, report_id)


@staff_router.get("/{report_id}/audio", response_class=FileResponse)
def report_audio(
    report_id: uuid.UUID, request: Request, session: Session = Depends(get_session)
) -> FileResponse:
    """The patient's original recording."""
    settings = request.app.state.settings
    path, media_type = service.audio_file(
        session, settings, current_doctor(session).hospital_id, report_id
    )
    return FileResponse(path, media_type=media_type)
