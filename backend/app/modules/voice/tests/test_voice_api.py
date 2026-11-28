from typing import Any

from fastapi.testclient import TestClient

from app.providers.base import ProviderError, ProviderKind, Transcript

RAMESH = (
    "Ramesh, 68, cataract right eye, standard template, "
    "diabetic so check sugar daily, language Kannada."
)


def patient_token(client: TestClient) -> str:
    card = client.post("/api/v1/discharges/extract", json={"transcript": RAMESH}).json()["card"]
    discharge_id = client.post("/api/v1/discharges", json=card).json()["id"]
    client.post(f"/api/v1/discharges/{discharge_id}/approve")
    links = client.post(f"/api/v1/delivery/discharges/{discharge_id}/links").json()
    url: str = links[0]["url"]
    return url.removeprefix("/p/")


class FakeTTS:
    name = "sarvam"
    client_side = False
    voice_id = "sarvam:test"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def speak(self, text: str, lang: str) -> bytes:
        self.calls.append((text, lang))
        return b"ID3-mp3-" + text.encode()


class FakeSTT:
    name = "sarvam"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[bytes, str | None, str | None]] = []

    async def transcribe(
        self, audio: bytes, lang_hint: str | None, mime_type: str | None = None
    ) -> Transcript:
        self.calls.append((audio, lang_hint, mime_type))
        if self.fail:
            raise ProviderError("down")
        return Transcript(text="ಕಣ್ಣು ಕೆಂಪಾಗಿದೆ", language="kn", confidence=None)


def install(client: TestClient, kind: ProviderKind, provider: Any) -> None:
    client.app.state.providers._active[kind] = provider  # type: ignore[attr-defined]


def test_demo_mode_leaves_speech_to_the_browser(client: TestClient) -> None:
    token = patient_token(client)
    res = client.post(f"/api/v1/patient/{token}/speak", json={"text": "ನಮಸ್ಕಾರ", "language": "kn"})
    assert res.status_code == 409 and res.json()["error"]["code"] == "browser_speech"
    res = client.post(
        "/api/v1/voice/transcribe", content=b"x", headers={"content-type": "audio/webm"}
    )
    assert res.status_code == 409


def test_spoken_audio_is_made_once_and_cached(client: TestClient) -> None:
    tts = FakeTTS()
    install(client, ProviderKind.tts, tts)
    token = patient_token(client)
    body = {"text": "ಇಂದೇ ಆಸ್ಪತ್ರೆಗೆ ಬನ್ನಿ", "language": "kn-IN"}
    first = client.post(f"/api/v1/patient/{token}/speak", json=body)
    second = client.post(f"/api/v1/patient/{token}/speak", json=body)
    assert first.status_code == 200 and first.headers["content-type"] == "audio/mpeg"
    assert first.content == second.content == "ID3-mp3-ಇಂದೇ ಆಸ್ಪತ್ರೆಗೆ ಬನ್ನಿ".encode()
    assert (first.headers["x-audio-cache"], second.headers["x-audio-cache"]) == ("miss", "hit")
    assert tts.calls == [("ಇಂದೇ ಆಸ್ಪತ್ರೆಗೆ ಬನ್ನಿ", "kn")]
    # A different language is different audio.
    client.post(f"/api/v1/patient/{token}/speak", json={**body, "language": "hi"})
    assert len(tts.calls) == 2


def test_speech_needs_a_valid_patient_link(client: TestClient) -> None:
    install(client, ProviderKind.tts, FakeTTS())
    res = client.post(
        "/api/v1/patient/not-a-real-token-123/speak", json={"text": "x", "language": "kn"}
    )
    assert res.status_code == 404


def test_server_transcription(client: TestClient) -> None:
    stt = FakeSTT()
    install(client, ProviderKind.stt, stt)
    res = client.post(
        "/api/v1/voice/transcribe",
        params={"lang": "kn"},
        content=b"webm-bytes",
        headers={"content-type": "audio/webm;codecs=opus"},
    )
    assert res.status_code == 200
    assert res.json() == {"text": "ಕಣ್ಣು ಕೆಂಪಾಗಿದೆ", "language": "kn", "confidence": None}
    assert stt.calls == [(b"webm-bytes", "kn", "audio/webm")]


def test_transcription_rejects_bad_input_and_reports_outages(client: TestClient) -> None:
    install(client, ProviderKind.stt, FakeSTT(fail=True))
    url = "/api/v1/voice/transcribe"
    assert client.post(url, content=b"x", headers={"content-type": "text/plain"}).status_code == 415
    assert client.post(url, content=b"", headers={"content-type": "audio/webm"}).status_code == 422
    big = client.post(url, content=b"x" * 2_000_001, headers={"content-type": "audio/webm"})
    assert big.status_code == 413
    down = client.post(url, content=b"x", headers={"content-type": "audio/webm"})
    assert down.status_code == 503 and down.json()["error"]["code"] == "speech_unavailable"
