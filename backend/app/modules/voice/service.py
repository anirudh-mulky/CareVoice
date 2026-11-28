"""Server-side speech (real mode): transcribe a recording, and speak text in the patient's
language with the configured TTS provider. In demo mode the browser does both, and these
calls answer 409 browser_speech so the client keeps using it."""

import hashlib
import logging
import os
from pathlib import Path

from app.core.config import Settings
from app.core.errors import AppError
from app.providers.base import ProviderError
from app.providers.registry import ProviderRegistry
from app.rules.lexicon import get_lexicon

logger = logging.getLogger("carevoice.voice")
AUDIO_TYPES = ("audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav", "audio/x-wav")


def browser_speech() -> AppError:
    return AppError(409, "browser_speech", "Speech runs in the browser in this mode.")


def server_stt(providers: ProviderRegistry) -> bool:
    return getattr(providers.stt, "name", "demo") != "demo"


def server_tts(providers: ProviderRegistry) -> bool:
    return not getattr(providers.tts, "client_side", True)


async def transcribe(
    providers: ProviderRegistry,
    settings: Settings,
    audio: bytes,
    content_type: str,
    lang: str | None,
) -> tuple[str, str, float | None]:
    if not server_stt(providers):
        raise browser_speech()
    mime = content_type.split(";")[0].strip().lower()
    if mime not in AUDIO_TYPES:
        raise AppError(415, "unsupported_audio", "Send webm, ogg, mp4, mp3 or wav audio.")
    if not audio:
        raise AppError(422, "empty_audio", "The recording is empty.")
    if len(audio) > settings.report_audio_max_bytes:
        raise AppError(413, "audio_too_large", "The recording is too long.")
    try:
        result = await providers.stt.transcribe(audio, lang, mime)
    except ProviderError as exc:
        # The client falls back to browser speech or "type instead".
        raise AppError(503, "speech_unavailable", "Speech recognition is not available.") from exc
    return result.text, result.language, result.confidence


def cache_path(settings: Settings, voice_id: str, lang: str, text: str) -> Path:
    key = hashlib.sha256(f"{voice_id}\n{lang}\n{text}".encode()).hexdigest()
    return Path(settings.media_dir) / "tts" / f"{key}.mp3"


async def speak(
    providers: ProviderRegistry, settings: Settings, text: str, lang: str
) -> tuple[bytes, bool]:
    """MP3 audio for `text`; the second value says whether it came from the cache."""
    if not server_tts(providers):
        raise browser_speech()
    lang = lang.split("-")[0].lower()
    if lang not in get_lexicon().languages:
        raise AppError(422, "unknown_language", "Unsupported language.")
    text = text.strip()
    tts = providers.tts
    path = cache_path(settings, getattr(tts, "voice_id", tts.name), lang, text)
    if path.exists():
        return path.read_bytes(), True
    try:
        audio = await tts.speak(text, lang)
    except ProviderError as exc:
        raise AppError(503, "speech_unavailable", "Spoken audio is not available.") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_bytes(audio)
    os.replace(tmp, path)  # never serve a half-written file
    return audio, False
