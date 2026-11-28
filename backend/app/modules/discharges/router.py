import uuid

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session

from app.core.context import current_doctor
from app.core.db import get_session
from app.core.models import DischargeStatus
from app.modules.discharges import service
from app.modules.discharges.schemas import (
    ApproveResult,
    DischargeCard,
    DischargeListItem,
    DischargeOut,
    ExtractRequest,
    ExtractResponse,
    TemplateOption,
)

router = APIRouter(prefix="/api/v1/discharges", tags=["discharges"])


@router.post("/extract", response_model=ExtractResponse)
async def extract_discharge(
    body: ExtractRequest, request: Request, session: Session = Depends(get_session)
) -> ExtractResponse:
    """The doctor's spoken sentence -> a draft card with unclear fields. Nothing is saved."""
    staff = current_doctor(session)
    return await service.extract(session, staff, request.app.state.providers, body.transcript)


@router.get("/templates", response_model=list[TemplateOption])
def discharge_templates(session: Session = Depends(get_session)) -> list[TemplateOption]:
    """Templates the card's template picker offers (latest version of each)."""
    return service.template_options(session, current_doctor(session).hospital_id)


@router.post("", response_model=DischargeOut, status_code=201)
def create_draft(card: DischargeCard, session: Session = Depends(get_session)) -> DischargeOut:
    return service.create_draft(session, current_doctor(session), card)


@router.patch("/{discharge_id}", response_model=DischargeOut)
def update_draft(
    discharge_id: uuid.UUID, card: DischargeCard, session: Session = Depends(get_session)
) -> DischargeOut:
    return service.update_draft(session, current_doctor(session), discharge_id, card)


@router.post("/{discharge_id}/approve", response_model=ApproveResult)
def approve_discharge(
    discharge_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=200),
) -> ApproveResult:
    """Blocked while unclear fields remain. Repeating it (double tap) never sends twice."""
    return service.approve(session, current_doctor(session), request.app.state.bus, discharge_id)


@router.get("", response_model=list[DischargeListItem])
def list_discharges(
    status: DischargeStatus | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100, description="Search by patient name"),
    session: Session = Depends(get_session),
) -> list[DischargeListItem]:
    """Dashboard list: alerts first, filter by status, search by name."""
    return service.list_discharges(session, current_doctor(session), status, q)


@router.get("/{discharge_id}", response_model=DischargeOut)
def get_discharge(discharge_id: uuid.UUID, session: Session = Depends(get_session)) -> DischargeOut:
    return service.get_discharge(session, current_doctor(session), discharge_id)
