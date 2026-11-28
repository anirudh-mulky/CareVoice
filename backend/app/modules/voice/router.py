from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.errors import AppError
from app.core.patient_access import resolve_token
from app.modules.voice import service
from app.modules.voice.schemas import SpeakIn, TranscriptOut

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])
patient_router = APIRouter(prefix="/api/v1/patient", tags=["patient"])


@router.post("/transcribe", response_model=TranscriptOut)
async def transcribe(
    request: Request, lang: str | None = Query(default=None, max_length=8)
) -> TranscriptOut:
    """Raw audio body (Content-Type: audio/webm, max 2 MB) -> text, language, confidence.

    Real mode only; in demo mode this answers 409 browser_speech.
    """
    settings = request.app.state.settings
    if int(request.headers.get("content-length") or 0) > settings.report_audio_max_bytes:
        raise AppError(413, "audio_too_large", "The recording is too long.")
    text, language, confidence = await service.transcribe(
        request.app.state.providers,
        settings,
        await request.body(),
        request.headers.get("content-type", ""),
        lang,
    )
    return TranscriptOut(text=text, language=language, confidence=confidence)


@patient_router.post(
    "/{token}/speak",
    response_class=Response,
    responses={200: {"content": {"audio/mpeg": {}}}},
)
async def speak(
    token: str, body: SpeakIn, request: Request, session: Session = Depends(get_session)
) -> Response:
    """Spoken audio (MP3) for text on the patient's screen, cached per text and language.

    Only through a valid patient link, so the provider can't be used by anyone else.
    """
    resolve_token(session, token)
    audio, cached = await service.speak(
        request.app.state.providers, request.app.state.settings, body.text, body.language
    )
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "private, max-age=86400",
            "X-Audio-Cache": "hit" if cached else "miss",
        },
    )
