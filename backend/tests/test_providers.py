from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.providers.base import (
    LLM,
    ProviderError,
    ProviderKind,
    ProviderState,
    STTProvider,
    Translator,
    TTSProvider,
)
from app.providers.llm.demo import DemoLLM
from app.providers.registry import REAL_PROVIDERS, ProviderRegistry, RealSpec
from app.providers.stt.demo import DemoSTT
from app.providers.translate.demo import DemoTranslator
from app.providers.tts.demo import DemoTTS
from tests.support import make_settings

pytestmark = pytest.mark.anyio


def settings(tmp_path: Path, **kw: Any) -> Settings:
    return make_settings(tmp_path, **kw)


# --- Demo STT ---------------------------------------------------------------


async def test_demo_stt_echoes_the_browser_transcript() -> None:
    result = await DemoSTT().transcribe(b"Kannu tumba kempagide", "kn")
    assert result.text == "Kannu tumba kempagide"
    assert result.language == "kn"
    assert result.confidence == 1.0


async def test_demo_stt_keeps_native_script() -> None:
    result = await DemoSTT().transcribe("ಕಣ್ಣು ಕೆಂಪಾಗಿದೆ".encode(), "kn")
    assert result.text == "ಕಣ್ಣು ಕೆಂಪಾಗಿದೆ"


async def test_demo_stt_cannot_hear_real_audio() -> None:
    webm_header = b"\x1aE\xdf\xa3\x9fB\x86\x81\x01"
    result = await DemoSTT().transcribe(webm_header, "hi")
    assert result.text == ""
    assert result.confidence == 0.0  # decision rules will ask the patient again


async def test_demo_stt_defaults_language_to_english() -> None:
    assert (await DemoSTT().transcribe(b"my eye hurts", None)).language == "en"


# --- Demo TTS ---------------------------------------------------------------


async def test_demo_tts_leaves_speaking_to_the_browser() -> None:
    tts = DemoTTS()
    assert await tts.speak("ನಮಸ್ಕಾರ", "kn") == b""
    assert tts.client_side is True


# --- Demo translator -------------------------------------------------------


async def test_demo_translator_looks_up_known_phrases() -> None:
    t = DemoTranslator()
    assert await t.translate("Please come to the hospital today.", "en", "kn") == (
        "ದಯವಿಟ್ಟು ಇಂದೇ ಆಸ್ಪತ್ರೆಗೆ ಬನ್ನಿ."
    )


async def test_demo_translator_works_towards_english_for_the_doctor() -> None:
    t = DemoTranslator()
    english = await t.translate("Kannu tumba kempagide, novu ide.", "kn-Latn", "en")
    assert english == "My eye is very red and it hurts."


async def test_demo_translator_ignores_case_spacing_and_end_punctuation() -> None:
    t = DemoTranslator()
    assert await t.translate("  please come to the HOSPITAL   today ", "en", "hi") == (
        "कृपया आज ही अस्पताल आएँ।"
    )


async def test_demo_translator_never_invents_a_translation() -> None:
    t = DemoTranslator()
    text = "Take 2 drops of a medicine nobody wrote down"
    assert await t.translate(text, "en", "ta") == text
    assert t.lookup(text, "en", "ta") is None


async def test_demo_translator_same_language_is_unchanged() -> None:
    assert await DemoTranslator().translate("ನಮಸ್ಕಾರ", "kn", "kn") == "ನಮಸ್ಕಾರ"


async def test_demo_translator_accepts_runtime_phrases() -> None:
    t = DemoTranslator(phrases_file=None)
    t.add("rf_redness", "en", "Increasing redness of the eye")
    t.add("rf_redness", "kn", "ಕಣ್ಣು ಹೆಚ್ಚು ಕೆಂಪಾಗುತ್ತಿದ್ದರೆ")
    assert await t.translate("Increasing redness of the eye", "en", "kn") == (
        "ಕಣ್ಣು ಹೆಚ್ಚು ಕೆಂಪಾಗುತ್ತಿದ್ದರೆ"
    )


def test_every_phrase_has_english_and_the_patient_languages() -> None:
    t = DemoTranslator()
    core = ["visit_today", "not_heard", "is_that_right", "sent_to_doctor", "not_a_doctor"]
    for phrase_id in core:
        for lang in ("en", "kn", "hi", "ta"):
            assert (phrase_id, lang) in t._texts, (phrase_id, lang)


# --- Demo LLM ---------------------------------------------------------------


class Echo(BaseModel):
    summary_en: str
    confidence: str


async def test_demo_llm_returns_validated_schema_from_its_rule() -> None:
    llm = DemoLLM()
    llm.register_rule("echo", lambda prompt: {"summary_en": prompt, "confidence": "high"})
    result = await llm.json("echo", "red eye", Echo)
    assert result == Echo(summary_en="red eye", confidence="high")


async def test_demo_llm_rejects_invalid_rule_output() -> None:
    llm = DemoLLM()
    llm.register_rule("broken", lambda _prompt: {"summary_en": 3})
    with pytest.raises(ProviderError):
        await llm.json("broken", "x", Echo)


async def test_demo_llm_without_a_rule_raises_provider_error() -> None:
    with pytest.raises(ProviderError):
        await DemoLLM().json("analyse_symptom", "x", Echo)


def test_demo_providers_satisfy_the_interfaces() -> None:
    assert isinstance(DemoSTT(), STTProvider)
    assert isinstance(DemoTTS(), TTSProvider)
    assert isinstance(DemoTranslator(), Translator)
    assert isinstance(DemoLLM(), LLM)


# --- Registry ---------------------------------------------------------------


def test_default_config_runs_every_provider_in_demo(tmp_path: Path) -> None:
    registry = ProviderRegistry(settings(tmp_path))
    statuses = registry.statuses()
    assert [s.kind for s in statuses] == list(ProviderKind)
    assert all(s.mode == "demo" and s.status is ProviderState.ok for s in statuses)
    assert registry.any_key_missing is False
    assert isinstance(registry.stt, DemoSTT)
    assert isinstance(registry.llm, DemoLLM)


def test_demo_mode_ignores_real_provider_names_and_keys(tmp_path: Path) -> None:
    registry = ProviderRegistry(
        settings(tmp_path, provider_mode="demo", stt_provider="sarvam", sarvam_api_key="k")
    )
    stt = next(s for s in registry.statuses() if s.kind is ProviderKind.stt)
    assert stt.mode == "demo"
    assert stt.status is ProviderState.ok


@pytest.mark.parametrize(
    ("kind", "overrides"),
    [
        (ProviderKind.stt, {"stt_provider": "sarvam"}),
        (ProviderKind.tts, {"tts_provider": "bhashini"}),
        (ProviderKind.translator, {"translate_provider": "sarvam"}),
        (ProviderKind.llm, {"llm_provider": "anthropic"}),
    ],
)
def test_real_provider_without_key_falls_back_to_demo_and_reports_key_not_set(
    tmp_path: Path, kind: ProviderKind, overrides: dict[str, str]
) -> None:
    registry = ProviderRegistry(settings(tmp_path, provider_mode="real", **overrides))
    status = next(s for s in registry.statuses() if s.kind is kind)
    assert status.status is ProviderState.key_not_set
    assert status.mode == "demo"
    assert status.active == "demo"
    assert status.detail == "Key not set, using demo mode"
    assert registry.any_key_missing is True


def test_real_mode_with_browser_speech_is_fine(tmp_path: Path) -> None:
    registry = ProviderRegistry(settings(tmp_path, provider_mode="real"))
    assert all(s.status is ProviderState.ok for s in registry.statuses())


def test_unknown_provider_falls_back_to_demo(tmp_path: Path) -> None:
    registry = ProviderRegistry(settings(tmp_path, provider_mode="real", stt_provider="nope"))
    stt = next(s for s in registry.statuses() if s.kind is ProviderKind.stt)
    assert stt.status is ProviderState.unknown_provider
    assert isinstance(registry.stt, DemoSTT)


def test_key_present_but_adapter_not_built_falls_back(tmp_path: Path) -> None:
    registry = ProviderRegistry(
        settings(tmp_path, provider_mode="real", stt_provider="bhashini", bhashini_api_key="k")
    )
    stt = next(s for s in registry.statuses() if s.kind is ProviderKind.stt)
    assert stt.status is ProviderState.not_built
    assert isinstance(registry.stt, DemoSTT)


def test_real_adapter_is_used_when_key_and_factory_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeSarvam:
        name = "sarvam"

        def __init__(self, key: str) -> None:
            self.key = key

    monkeypatch.setitem(
        REAL_PROVIDERS[ProviderKind.stt],
        "sarvam",
        RealSpec("sarvam_api_key", lambda key, _s: FakeSarvam(key)),
    )
    registry = ProviderRegistry(
        settings(tmp_path, provider_mode="real", stt_provider="Sarvam", sarvam_api_key="k-1")
    )
    stt = next(s for s in registry.statuses() if s.kind is ProviderKind.stt)
    assert stt.mode == "real"
    assert stt.active == "sarvam"
    assert isinstance(registry.stt, FakeSarvam)
    assert registry.stt.key == "k-1"
    # The rule engine stays available as the LLM fallback.
    assert isinstance(registry.demo_llm, DemoLLM)


def test_keys_never_appear_in_status(tmp_path: Path) -> None:
    registry = ProviderRegistry(
        settings(tmp_path, provider_mode="real", stt_provider="sarvam", sarvam_api_key="sk-x9")
    )
    assert "sk-x9" not in str([s.model_dump() for s in registry.statuses()])
