"""Provider interfaces (spec: "Voice and AI pipeline").

Every external AI service sits behind one of these protocols, and each has a keyless
demo implementation, so the app always starts without secrets.
"""

from enum import StrEnum
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, Field

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class ProviderKind(StrEnum):
    stt = "stt"
    tts = "tts"
    translator = "translate"
    llm = "llm"


class ProviderState(StrEnum):
    ok = "ok"  # running as configured
    key_not_set = "key_not_set"  # real provider asked for without its key -> demo
    not_built = "not_built"  # key present but the adapter is not built yet -> demo
    unknown_provider = "unknown_provider"  # name not recognised -> demo


class Transcript(BaseModel):
    text: str
    language: str
    # None when the provider gives no confidence (Sarvam only rates language detection).
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ProviderStatus(BaseModel):
    kind: ProviderKind
    requested: str  # what config asked for, e.g. "sarvam"
    active: str  # what is actually running, e.g. "demo"
    mode: str  # "demo" or "real"
    status: ProviderState
    detail: str = ""


class ProviderError(RuntimeError):
    """A provider failed; callers fall back to demo or ask the user to retry."""


@runtime_checkable
class STTProvider(Protocol):
    name: str

    async def transcribe(
        self, audio: bytes, lang_hint: str | None, mime_type: str | None = None
    ) -> Transcript: ...


@runtime_checkable
class TTSProvider(Protocol):
    name: str

    async def speak(self, text: str, lang: str) -> bytes: ...


@runtime_checkable
class Translator(Protocol):
    name: str

    async def translate(self, text: str, src: str, dst: str) -> str: ...


@runtime_checkable
class LLM(Protocol):
    name: str

    async def json(self, task: str, prompt: str, schema: type[SchemaT]) -> SchemaT: ...
