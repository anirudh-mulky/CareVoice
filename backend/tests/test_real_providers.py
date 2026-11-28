"""Real provider adapters, against mocked HTTP (no keys, no network in tests)."""

import base64
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import anthropic
import httpx2
import pytest
from pydantic import BaseModel

from app.ai.tasks.score_teachback.schema import TeachBack
from app.core.config import Settings
from app.providers.base import ProviderError, ProviderKind, ProviderState
from app.providers.llm.anthropic import AnthropicLLM
from app.providers.registry import ProviderRegistry
from app.providers.sarvam.client import (
    SarvamClient,
    SarvamSTT,
    SarvamTranslator,
    SarvamTTS,
    chunks,
)
from app.providers.translate.llm import LLMTranslator
from tests.support import make_settings

Handler = Callable[[httpx2.Request], httpx2.Response]
pytestmark = pytest.mark.anyio


def sarvam(tmp_path: Path, handler: Handler) -> SarvamClient:
    return SarvamClient(
        "sk-test-123", make_settings(tmp_path), transport=httpx2.MockTransport(handler)
    )


# --- Sarvam -----------------------------------------------------------------------------------


async def test_sarvam_stt_sends_the_recording_and_reads_the_transcript(tmp_path: Path) -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(
            200,
            json={"request_id": "r1", "transcript": " ಕಣ್ಣು ಕೆಂಪಾಗಿದೆ ", "language_code": "kn-IN"},
        )

    result = await SarvamSTT(sarvam(tmp_path, handler)).transcribe(
        b"webm", "kn", "audio/webm;codecs=opus"
    )
    assert (result.text, result.language, result.confidence) == ("ಕಣ್ಣು ಕೆಂಪಾಗಿದೆ", "kn", None)
    request = seen[0]
    assert str(request.url) == "https://api.sarvam.ai/speech-to-text"
    assert request.headers["api-subscription-key"] == "sk-test-123"
    body = request.content.decode("latin-1")
    assert 'name="file"; filename="speech.webm"' in body
    assert 'name="model"\r\n\r\nsaaras:v4' in body
    assert 'name="language_code"\r\n\r\nkn-IN' in body


async def test_sarvam_stt_auto_detects_when_no_language_is_given(tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert 'name="language_code"\r\n\r\nunknown' in request.content.decode("latin-1")
        return httpx2.Response(
            200,
            json={"transcript": "आँख लाल है", "language_code": "hi-IN", "language_probability": 0.93},
        )

    result = await SarvamSTT(sarvam(tmp_path, handler)).transcribe(b"x", None, "audio/ogg")
    assert (result.language, result.confidence) == ("hi", 0.93)


async def test_sarvam_tts_joins_the_audio_of_long_texts(tmp_path: Path) -> None:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return httpx2.Response(
            200, json={"audios": [base64.b64encode(b"MP3-%d" % len(bodies)).decode()]}
        )

    long_text = ". ".join(["ಇಂದೇ ಆಸ್ಪತ್ರೆಗೆ ಬನ್ನಿ"] * 200) + "."
    audio = await SarvamTTS(sarvam(tmp_path, handler)).speak(long_text, "kn")
    assert len(bodies) >= 2 and all(len(b["text"]) <= 2500 for b in bodies)
    assert audio == b"".join(b"MP3-%d" % i for i in range(1, len(bodies) + 1))
    assert bodies[0] | {"text": ""} == {
        "text": "",
        "language_code": "kn-IN",
        "model": "bulbul:v3",
        "speaker": "shubh",
        "output_audio_codec": "mp3",
    }


async def test_sarvam_translate(tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(json.loads(request.content))
        return httpx2.Response(200, json={"translated_text": "ಪ್ರತಿದಿನ ಸಕ್ಕರೆ ಪರೀಕ್ಷಿಸಿ"})

    translator = SarvamTranslator(sarvam(tmp_path, handler))
    assert await translator.translate("Check sugar daily", "en", "kn") == "ಪ್ರತಿದಿನ ಸಕ್ಕರೆ ಪರೀಕ್ಷಿಸಿ"
    assert calls[0] == {
        "input": "Check sugar daily",
        "source_language_code": "en-IN",
        "target_language_code": "kn-IN",
        "model": "mayura:v1",
        "mode": "formal",
    }
    assert await translator.translate("Same", "en", "en-IN") == "Same"
    assert len(calls) == 1


async def test_sarvam_errors_become_provider_errors_without_the_key(tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            403, json={"error": {"code": "invalid_api_key_error", "message": "bad"}}
        )

    with pytest.raises(ProviderError) as err:
        await SarvamTranslator(sarvam(tmp_path, handler)).translate("Hi", "en", "kn")
    assert "invalid_api_key_error" in str(err.value) and "sk-test" not in str(err.value)


async def test_sarvam_network_failure_is_a_provider_error(tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("down")

    with pytest.raises(ProviderError):
        await SarvamTTS(sarvam(tmp_path, handler)).speak("ನಮಸ್ಕಾರ", "kn")


def test_long_texts_split_at_sentences() -> None:
    parts = chunks("One. Two. Three.", 9)
    assert parts == ["One. Two.", "Three."]
    assert all(len(p) <= 5 for p in chunks("x" * 12, 5))


# --- Claude -----------------------------------------------------------------------------------


def claude_reply(content: list[dict[str, Any]], stop_reason: str = "end_turn") -> dict[str, Any]:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def claude(tmp_path: Path, handler: Handler, **settings: Any) -> AnthropicLLM:
    client = anthropic.AsyncAnthropic(
        api_key="sk-ant-test",
        max_retries=0,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )
    return AnthropicLLM("sk-ant-test", make_settings(tmp_path, **settings), client=client)


async def test_claude_returns_schema_valid_json(tmp_path: Path) -> None:
    seen: list[httpx2.Request] = []
    answer = {"mentioned_flag_ids": ["rf_redness"], "missed_flag_ids": ["rf_pain"], "passed": False}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(
            200, json=claude_reply([{"type": "text", "text": json.dumps(answer)}])
        )

    result = await claude(tmp_path, handler).json("score_teachback", "PROMPT", TeachBack)
    assert result == TeachBack(**answer)
    body = json.loads(seen[0].content)
    assert body["model"] == "claude-opus-5-5"
    assert body["messages"] == [{"role": "user", "content": "PROMPT"}]
    assert body["output_config"]["effort"] == "low"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in seen[0].headers["anthropic-beta"]
    assert "sk-ant-test" in seen[0].headers["authorization"]  # the SDK handles auth


async def test_claude_model_comes_from_settings(tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert json.loads(request.content)["model"] == "claude-sonnet-5-5"
        text = json.dumps({"mentioned_flag_ids": [], "missed_flag_ids": [], "passed": True})
        return httpx2.Response(200, json=claude_reply([{"type": "text", "text": text}]))

    await claude(tmp_path, handler, llm_model="claude-sonnet-5-5").json("t", "P", TeachBack)


@pytest.mark.parametrize(
    "response",
    [
        httpx2.Response(200, json=claude_reply([], stop_reason="refusal")),
        httpx2.Response(
            529, json={"type": "error", "error": {"type": "overloaded_error", "message": "x"}}
        ),
        httpx2.Response(
            401, json={"type": "error", "error": {"type": "authentication_error", "message": "x"}}
        ),
    ],
)
async def test_claude_failures_become_provider_errors(
    tmp_path: Path, response: httpx2.Response
) -> None:
    llm = claude(tmp_path, lambda _r: response)
    with pytest.raises(ProviderError):
        await llm.json("score_teachback", "P", TeachBack)


async def test_llm_translation_uses_the_llm(tmp_path: Path) -> None:
    class FakeLLM:
        name = "fake"

        async def json(self, task: str, prompt: str, schema: type[BaseModel]) -> BaseModel:
            assert "from English to Kannada" in prompt and "Check sugar daily" in prompt
            return schema.model_validate({"translated_text": "ಪ್ರತಿದಿನ ಸಕ್ಕರೆ ಪರೀಕ್ಷಿಸಿ"})

    translator = LLMTranslator(FakeLLM())  # type: ignore[arg-type]  # a simplified LLM
    assert await translator.translate("Check sugar daily", "en", "kn") == "ಪ್ರತಿದಿನ ಸಕ್ಕರೆ ಪರೀಕ್ಷಿಸಿ"


# --- Registry: keys from the environment, demo without them -----------------------------------


def statuses(settings: Settings) -> dict[ProviderKind, Any]:
    return {s.kind: s for s in ProviderRegistry(settings).statuses()}


def test_with_keys_the_real_adapters_run(tmp_path: Path) -> None:
    registry = ProviderRegistry(
        make_settings(
            tmp_path,
            provider_mode="real",
            stt_provider="sarvam",
            tts_provider="sarvam",
            translate_provider="sarvam",
            sarvam_api_key="sk-x",
            llm_provider="anthropic",
            llm_api_key="sk-ant-x",
        )
    )
    assert registry.stt.name == "sarvam" and registry.tts.name == "sarvam"
    assert registry.llm.name == "anthropic"
    assert registry.translator.name == "sarvam"  # wrapped in failover, same name
    assert {s.mode for s in registry.statuses()} == {"real"}


def test_without_keys_nothing_changes_and_the_badge_says_key_not_set(tmp_path: Path) -> None:
    found = statuses(
        make_settings(
            tmp_path, provider_mode="real", stt_provider="sarvam", llm_provider="anthropic"
        )
    )
    assert found[ProviderKind.stt].status is ProviderState.key_not_set
    assert found[ProviderKind.llm].status is ProviderState.key_not_set
    assert found[ProviderKind.stt].active == "demo"


def test_llm_translation_needs_claude(tmp_path: Path) -> None:
    found = statuses(
        make_settings(
            tmp_path,
            provider_mode="real",
            translate_provider="llm",
            llm_provider="openai",
            llm_api_key="k",
        )
    )
    assert found[ProviderKind.translator].status is ProviderState.not_built
    assert "LLM_PROVIDER=anthropic" in found[ProviderKind.translator].detail
    ok = statuses(
        make_settings(
            tmp_path,
            provider_mode="real",
            translate_provider="llm",
            llm_provider="anthropic",
            llm_api_key="k",
        )
    )
    assert ok[ProviderKind.translator].mode == "real"


def test_keys_never_appear_in_the_status(tmp_path: Path) -> None:
    raw = json.dumps(
        [
            s.model_dump(mode="json")
            for s in ProviderRegistry(
                make_settings(
                    tmp_path,
                    provider_mode="real",
                    stt_provider="sarvam",
                    sarvam_api_key="sk-secret",
                )
            ).statuses()
        ]
    )
    assert "sk-secret" not in raw
