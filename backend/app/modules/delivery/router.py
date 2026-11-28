import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.context import current_doctor
from app.core.db import get_session
from app.core.patient_access import resolve_token
from app.modules.delivery import service
from app.modules.delivery.schemas import (
    ChatMessage,
    DemoPatientLink,
    LanguageChange,
    LanguageOut,
    PatientHome,
    PatientLink,
)

# Patient and carer pages: no login, the link token is the key.
patient_router = APIRouter(prefix="/api/v1/patient", tags=["patient"])
# Staff: share links for an approved discharge.
staff_router = APIRouter(prefix="/api/v1/delivery", tags=["delivery"])
demo_router = APIRouter(prefix="/api/v1/delivery", tags=["demo"])


@patient_router.get("/{token}", response_model=PatientHome)
async def patient_home(
    token: str, request: Request, session: Session = Depends(get_session)
) -> PatientHome:
    """Patient home: the care card in their language, red flags first."""
    access = resolve_token(session, token)
    return await service.patient_home(session, request.app.state.providers, access)


@patient_router.get("/{token}/messages", response_model=list[ChatMessage])
def patient_messages(token: str, session: Session = Depends(get_session)) -> list[ChatMessage]:
    """The WhatsApp-style chat for this care episode (same for patient and carer)."""
    return service.chat(session, resolve_token(session, token))


@patient_router.post("/{token}/messages/{message_id}/played", status_code=204)
def message_played(
    token: str, message_id: uuid.UUID, request: Request, session: Session = Depends(get_session)
) -> Response:
    """Record that a voice note was played (families replaying is a pilot success measure)."""
    service.mark_played(session, request.app.state.bus, resolve_token(session, token), message_id)
    return Response(status_code=204)


@patient_router.put("/{token}/language", response_model=LanguageOut)
def change_language(
    token: str, body: LanguageChange, request: Request, session: Session = Depends(get_session)
) -> LanguageOut:
    """Wrong language? The patient (or carer) taps or says theirs; the app switches."""
    access = resolve_token(session, token)
    code = service.change_language(
        session, request.app.state.bus, access, body.language, body.spoken
    )
    return LanguageOut(language=code)


@staff_router.post("/discharges/{discharge_id}/links", response_model=list[PatientLink])
def share_links(
    discharge_id: uuid.UUID, session: Session = Depends(get_session)
) -> list[PatientLink]:
    """Fresh patient and carer links for an approved discharge (old links keep working)."""
    return service.issue_links(session, current_doctor(session).hospital_id, discharge_id)


@demo_router.get("/demo-links", response_model=list[DemoPatientLink])
def demo_links(session: Session = Depends(get_session)) -> list[DemoPatientLink]:
    """Demo only: links for every sent discharge, for the patient picker."""
    return service.demo_links(session, current_doctor(session).hospital_id)
