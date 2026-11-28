"""Demo STT: speech is recognised in the browser (Web Speech API), so the server echoes it.

The client uploads the browser's transcript as UTF-8 text in place of audio. Real audio
cannot be transcribed without a provider, so it comes back empty with zero confidence,
which the decision rules treat as "ask again".
"""

from app.providers.base import Transcript

DEFAULT_LANGUAGE = "en"


class DemoSTT:
    name = "demo"

    async def transcribe(
        self, audio: bytes, lang_hint: str | None, mime_type: str | None = None
    ) -> Transcript:
        language = lang_hint or DEFAULT_LANGUAGE
        try:
            text = audio.decode("utf-8").strip()
        except UnicodeDecodeError:
            return Transcript(text="", language=language, confidence=0.0)
        if not text or not text.isprintable():
            return Transcript(text="", language=language, confidence=0.0)
        return Transcript(text=text, language=language, confidence=1.0)
