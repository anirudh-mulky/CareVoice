from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.patient_access import resolve_token
from app.modules.teachback import service
from app.modules.teachback.schemas import TeachbackAnswer, TeachbackResult, TeachbackState

# Patient and carer pages: no login, the link token is the key.
router = APIRouter(prefix="/api/v1/patient", tags=["patient"])


@router.get("/{token}/teachback", response_model=TeachbackState)
def teachback_state(
    token: str, request: Request, session: Session = Depends(get_session)
) -> TeachbackState:
    """The question in the patient's language, tries used, and the last result."""
    return service.state(session, request.app.state.settings, resolve_token(session, token))


@router.post("/{token}/teachback", response_model=TeachbackResult)
async def teachback_answer(
    token: str, body: TeachbackAnswer, request: Request, session: Session = Depends(get_session)
) -> TeachbackResult:
    """Score a spoken answer: re-explain missed warning signs, set understood or follow-up."""
    state = request.app.state
    return await service.answer(
        session, state.bus, state.providers, state.settings, resolve_token(session, token), body
    )
