"""Sarvam AI (https://docs.sarvam.ai): Indian-language speech-to-text, text-to-speech and
translation over REST. One shared HTTP client; errors become ProviderError so callers fall
back to browser speech or the phrasebook.
"""

import base64
import logging
import re
from typing import Any

import httpx2

from app.core.config import Settings
from app.providers.base import ProviderError, Transcript

logger = logging.getLogger("carevoice.providers.sarvam")
BASE_URL = "https://api.sarvam.ai"
TTS_MAX_CHARS = 2400  # API limit 2500
TRANSLATE_MAX_CHARS = 950  # mayura:v1 limit 1000
EXTENSIONS = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
}


def bcp47(lang: str) -> str:
    """'kn' -> 'kn-IN' (Sarvam uses BCP-47 codes)."""
    base = lang.split("-")[0].lower()
    return f"{base}-IN"


def chunks(text: str, limit: int) -> list[str]:
    """Split at sentence ends so each piece fits the API's length limit."""
    if len(text) <= limit:
        return [text]
    out, current = [], ""
    for sentence in re.split(r"(?<=[.!?।])\s+", text):
        while len(sentence) > limit:  # one very long sentence: hard split
            out.append(sentence[:limit])
            sentence = sentence[limit:]
        if current and len(current) + 1 + len(sentence) > limit:
            out.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        out.append(current)
    return out


class SarvamClient:
    def __init__(
        self, api_key: str, settings: Settings, transport: httpx2.AsyncBaseTransport | None = None
    ) -> None:
        self.settings = settings
        self.http = httpx2.AsyncClient(
            base_url=BASE_URL,
            headers={"api-subscription-key": api_key},
            timeout=settings.provider_timeout_seconds,
            transport=transport,
        )

    async def post(self, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await self.http.post(path, **kwargs)
        except httpx2.HTTPError as exc:
            raise ProviderError(f"Sarvam {path}: {type(exc).__name__}") from exc
        if response.status_code >= 400:
            try:
                error = response.json().get("error", {})
            except ValueError:
                error = {}
            # Never log the key or the patient's words; the code and status are enough.
            logger.warning("Sarvam %s failed: %s %s", path, response.status_code, error.get("code"))
            raise ProviderError(f"Sarvam {path}: {response.status_code} {error.get('code', '')}")
        data: dict[str, Any] = response.json()
        return data


class SarvamSTT:
    name = "sarvam"

    def __init__(self, client: SarvamClient) -> None:
        self.client = client

    async def transcribe(
        self, audio: bytes, lang_hint: str | None, mime_type: str | None = None
    ) -> Transcript:
        mime = (mime_type or "audio/webm").split(";")[0].strip().lower()
        filename = f"speech.{EXTENSIONS.get(mime, 'webm')}"
        data = await self.client.post(
            "/speech-to-text",
            files={"file": (filename, audio, mime)},
            data={
                "model": self.client.settings.sarvam_stt_model,
                "mode": "transcribe",
                # "unknown" lets Sarvam detect the language (a patient may switch).
                "language_code": bcp47(lang_hint) if lang_hint else "unknown",
            },
        )
        code = data.get("language_code") or lang_hint or "en"
        probability = data.get("language_probability")
        return Transcript(
            text=str(data.get("transcript") or "").strip(),
            language=str(code).split("-")[0],
            confidence=float(probability) if probability is not None else None,
        )


class SarvamTTS:
    name = "sarvam"
    client_side = False
    mime_type = "audio/mpeg"

    def __init__(self, client: SarvamClient) -> None:
        self.client = client

    @property
    def voice_id(self) -> str:
        """Part of the audio cache key: a new model or speaker means new audio."""
        s = self.client.settings
        return f"sarvam:{s.sarvam_tts_model}:{s.sarvam_tts_speaker}"

    async def speak(self, text: str, lang: str) -> bytes:
        audio = b""
        for piece in chunks(text.strip(), TTS_MAX_CHARS):
            data = await self.client.post(
                "/text-to-speech",
                json={
                    "text": piece,
                    "language_code": bcp47(lang),
                    "model": self.client.settings.sarvam_tts_model,
                    "speaker": self.client.settings.sarvam_tts_speaker,
                    "output_audio_codec": "mp3",
                },
            )
            # MP3 frames concatenate cleanly, so long texts become one clip.
            audio += b"".join(base64.b64decode(a) for a in data.get("audios", []))
        if not audio:
            raise ProviderError("Sarvam returned no audio")
        return audio


class SarvamTranslator:
    name = "sarvam"

    def __init__(self, client: SarvamClient) -> None:
        self.client = client

    async def translate(self, text: str, src: str, dst: str) -> str:
        if src.split("-")[0] == dst.split("-")[0] or not text.strip():
            return text
        out = []
        for piece in chunks(text.strip(), TRANSLATE_MAX_CHARS):
            data = await self.client.post(
                "/translate",
                json={
                    "input": piece,
                    "source_language_code": bcp47(src),
                    "target_language_code": bcp47(dst),
                    "model": self.client.settings.sarvam_translate_model,
                    "mode": "formal",
                },
            )
            out.append(str(data.get("translated_text") or ""))
        translated = " ".join(p for p in out if p).strip()
        if not translated:
            raise ProviderError("Sarvam returned no translation")
        return translated
