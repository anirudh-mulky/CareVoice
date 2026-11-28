"""Provider registry: picks STT, TTS, Translator and LLM implementations from config.

Rules:
- PROVIDER_MODE=demo -> every provider is the keyless demo version.
- PROVIDER_MODE=real -> the named provider, if its key is set and its adapter exists.
  A missing key reports key_not_set and falls back to demo; the app never fails to start.
Real adapters are added to REAL_PROVIDERS (Part 12) without changing any caller.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Request

from app.core.config import Settings
from app.providers.base import (
    LLM,
    ProviderError,
    ProviderKind,
    ProviderState,
    ProviderStatus,
    STTProvider,
    Translator,
    TTSProvider,
)
from app.providers.failover import (
    FailingLLM,
    FailingTranslator,
    FailoverTranslator,
    simulated,
)
from app.providers.llm.anthropic import AnthropicLLM
from app.providers.llm.demo import DemoLLM
from app.providers.sarvam.client import (
    SarvamClient,
    SarvamSTT,
    SarvamTranslator,
    SarvamTTS,
)
from app.providers.stt.demo import DemoSTT
from app.providers.translate.demo import DemoTranslator
from app.providers.translate.llm import LLMTranslator
from app.providers.tts.demo import DemoTTS

logger = logging.getLogger("carevoice.providers")

# Names that mean "use the keyless version" (browser = speech runs in the patient's browser).
DEMO_NAMES = {"", "demo", "browser", "rules"}

Factory = Callable[[str, Settings], Any]  # (api_key, settings) -> provider instance


@dataclass(frozen=True)
class RealSpec:
    key_setting: str  # Settings attribute holding the API key
    factory: Factory | None = None  # None until the adapter is built (Part 12)


def _llm(api_key: str, settings: Settings) -> Any:
    """The configured LLM adapter (only Claude is built so far)."""
    if settings.llm_provider != "anthropic":
        raise ProviderError(
            f"LLM translation needs LLM_PROVIDER=anthropic, not {settings.llm_provider!r}"
        )
    return AnthropicLLM(api_key, settings)


REAL_PROVIDERS: dict[ProviderKind, dict[str, RealSpec]] = {
    ProviderKind.stt: {
        "sarvam": RealSpec("sarvam_api_key", lambda key, s: SarvamSTT(SarvamClient(key, s))),
        "bhashini": RealSpec("bhashini_api_key"),
    },
    ProviderKind.tts: {
        "sarvam": RealSpec("sarvam_api_key", lambda key, s: SarvamTTS(SarvamClient(key, s))),
        "bhashini": RealSpec("bhashini_api_key"),
    },
    ProviderKind.translator: {
        "sarvam": RealSpec("sarvam_api_key", lambda key, s: SarvamTranslator(SarvamClient(key, s))),
        "bhashini": RealSpec("bhashini_api_key"),
        # Translate live texts with the configured LLM (one Anthropic key is enough).
        "llm": RealSpec("llm_api_key", lambda key, s: LLMTranslator(_llm(key, s))),
    },
    ProviderKind.llm: {
        "anthropic": RealSpec("llm_api_key", lambda key, s: AnthropicLLM(key, s)),
        "openai": RealSpec("llm_api_key"),
        "gemini": RealSpec("llm_api_key"),
    },
}


def _requested(settings: Settings, kind: ProviderKind) -> str:
    name = {
        ProviderKind.stt: settings.stt_provider,
        ProviderKind.tts: settings.tts_provider,
        ProviderKind.translator: settings.translate_provider,
        ProviderKind.llm: settings.llm_provider,
    }[kind]
    return name.strip().lower()


def _secret(settings: Settings, key_setting: str) -> str:
    value = getattr(settings, key_setting)
    return str(value.get_secret_value() if hasattr(value, "get_secret_value") else value)


class ProviderRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._demo: dict[ProviderKind, Any] = {
            ProviderKind.stt: DemoSTT(),
            ProviderKind.tts: DemoTTS(),
            ProviderKind.translator: DemoTranslator(),
            ProviderKind.llm: DemoLLM(),
        }
        self._active: dict[ProviderKind, Any] = {}
        self._status: dict[ProviderKind, ProviderStatus] = {}
        for kind in ProviderKind:
            self._active[kind], self._status[kind] = self._resolve(kind)
        self._simulate_failures(simulated(settings.simulate_failures))
        # Translation fails over to the phrasebook, then keeps the original wording.
        self._active[ProviderKind.translator] = FailoverTranslator(
            self._active[ProviderKind.translator], self._demo[ProviderKind.translator]
        )

    def _simulate_failures(self, names: frozenset[str]) -> None:
        fakes: dict[str, tuple[ProviderKind, FailingLLM | FailingTranslator]] = {
            "llm": (ProviderKind.llm, FailingLLM()),
            "translate": (ProviderKind.translator, FailingTranslator()),
        }
        for name in names:
            kind, fake = fakes[name]
            logger.warning("SIMULATE_FAILURES: %s provider will fail on every call", kind)
            self._active[kind] = fake
            self._status[kind] = self._status[kind].model_copy(
                update={"active": fake.name, "detail": "Simulated failure (SIMULATE_FAILURES)"}
            )

    def _resolve(self, kind: ProviderKind) -> tuple[Any, ProviderStatus]:
        requested = _requested(self.settings, kind)
        demo = self._demo[kind]

        def fallback(state: ProviderState, detail: str) -> tuple[Any, ProviderStatus]:
            if state is not ProviderState.ok:
                logger.warning("%s provider %r: %s", kind, requested, detail)
            status = ProviderStatus(
                kind=kind,
                requested=requested or "demo",
                active=demo.name,
                mode="demo",
                status=state,
                detail=detail,
            )
            return demo, status

        if self.settings.provider_mode == "demo" or requested in DEMO_NAMES:
            return fallback(ProviderState.ok, "Demo mode")

        spec = REAL_PROVIDERS[kind].get(requested)
        if spec is None:
            return fallback(ProviderState.unknown_provider, "Unknown provider")
        api_key = _secret(self.settings, spec.key_setting)
        if not api_key:
            return fallback(ProviderState.key_not_set, "Key not set, using demo mode")
        if spec.factory is None:
            return fallback(ProviderState.not_built, "Adapter not built yet, using demo mode")

        try:
            provider = spec.factory(api_key, self.settings)
        except Exception as exc:  # noqa: BLE001 - a broken setup must never stop the app
            return fallback(ProviderState.not_built, f"Could not start: {exc}")
        return provider, ProviderStatus(
            kind=kind,
            requested=requested,
            active=requested,
            mode="real",
            status=ProviderState.ok,
        )

    @property
    def stt(self) -> STTProvider:
        provider: STTProvider = self._active[ProviderKind.stt]
        return provider

    @property
    def tts(self) -> TTSProvider:
        provider: TTSProvider = self._active[ProviderKind.tts]
        return provider

    @property
    def translator(self) -> Translator:
        provider: Translator = self._active[ProviderKind.translator]
        return provider

    @property
    def llm(self) -> LLM:
        provider: LLM = self._active[ProviderKind.llm]
        return provider

    @property
    def demo_llm(self) -> DemoLLM:
        """The rule engine, also the fallback when a real LLM fails or returns bad JSON."""
        llm: DemoLLM = self._demo[ProviderKind.llm]
        return llm

    @property
    def demo_translator(self) -> DemoTranslator:
        translator: DemoTranslator = self._demo[ProviderKind.translator]
        return translator

    def statuses(self) -> list[ProviderStatus]:
        return [self._status[kind] for kind in ProviderKind]

    @property
    def any_key_missing(self) -> bool:
        return any(s.status is ProviderState.key_not_set for s in self._status.values())


def get_providers(request: Request) -> ProviderRegistry:
    """FastAPI dependency."""
    registry: ProviderRegistry = request.app.state.providers
    return registry
