/** Part 12: in real mode the voice components use the server's speech, with browser fallback. */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, vi } from "vitest";
import { AudioPlayer } from "./AudioPlayer";
import { type VoiceServices, VoiceServicesContext } from "./voiceServices";
import { VoiceInput } from "./VoiceInput";
import { installSynthesis, removeRecognition, removeSynthesis, voice } from "@/test/fakeSpeech";

let clipOk = true;
vi.mock("./Recorder", () => {
  class RecorderError extends Error {
    code = "failed";
  }
  class Recorder {
    async start() {}
    async stop() {
      return {
        blob: new Blob(["webm"], { type: "audio/webm" }),
        mimeType: "audio/webm;codecs=opus",
        durationMs: 2000,
        peakRms: 0.2,
        check: clipOk ? { ok: true } : { ok: false, problem: "silent" },
      };
    }
    cancel() {}
  }
  return { Recorder, RecorderError, isRecordingSupported: () => true };
});

const play = vi.fn(() => Promise.resolve());

beforeEach(() => {
  clipOk = true;
  play.mockClear();
  Object.defineProperty(HTMLMediaElement.prototype, "play", { configurable: true, value: play });
  Object.defineProperty(HTMLMediaElement.prototype, "pause", { configurable: true, value: () => {} });
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:audio", revokeObjectURL: () => {} }));
});

afterEach(() => {
  removeSynthesis();
  removeRecognition();
});

function withServices(services: VoiceServices, ui: React.ReactNode) {
  return render(<VoiceServicesContext.Provider value={services}>{ui}</VoiceServicesContext.Provider>);
}

test("real mode plays the server's Kannada voice instead of the browser's", async () => {
  const spoken = installSynthesis([voice("kn-IN")]);
  const speak = vi.fn(async () => new Blob(["mp3"], { type: "audio/mpeg" }));
  withServices({ speak }, <AudioPlayer text="ಇಂದೇ ಆಸ್ಪತ್ರೆಗೆ ಬನ್ನಿ" lang="kn" />);
  await userEvent.click(screen.getByRole("button", { name: "ಕೇಳಿ" }));
  await waitFor(() => expect(play).toHaveBeenCalled());
  expect(speak).toHaveBeenCalledWith("ಇಂದೇ ಆಸ್ಪತ್ರೆಗೆ ಬನ್ನಿ", "kn");
  expect(spoken).toHaveLength(0);
});

test("if the server voice fails, the browser speaks instead", async () => {
  const spoken = installSynthesis([voice("kn-IN")]);
  const speak = vi.fn(async () => {
    throw new Error("503");
  });
  withServices({ speak }, <AudioPlayer text="ಇಂದೇ ಆಸ್ಪತ್ರೆಗೆ ಬನ್ನಿ" lang="kn" />);
  await userEvent.click(screen.getByRole("button", { name: "ಕೇಳಿ" }));
  await waitFor(() => expect(spoken.length).toBeGreaterThan(0));
});

test("real mode records and the server transcribes, even without browser recognition", async () => {
  removeRecognition();
  const transcribe = vi.fn(async () => ({ text: "ಕಣ್ಣು ಕೆಂಪಾಗಿದೆ", language: "kn", confidence: null }));
  const onText = vi.fn();
  withServices({ transcribe }, <VoiceInput lang="kn" onText={onText} />);
  const mic = screen.getByRole("button", { name: "ಒತ್ತಿ ಮಾತನಾಡಿ" });
  expect(mic).toBeEnabled();
  await userEvent.click(mic);
  await userEvent.click(await screen.findByRole("button", { name: "ನಿಲ್ಲಿಸಲು ಒತ್ತಿ" }));
  await waitFor(() => expect(onText).toHaveBeenCalled());
  expect(onText.mock.calls[0]?.[0]).toBe("ಕಣ್ಣು ಕೆಂಪಾಗಿದೆ");
  const [blob, mime, lang] = transcribe.mock.calls[0] as unknown as [Blob, string, string];
  expect(blob).toBeInstanceOf(Blob);
  expect([mime, lang]).toEqual(["audio/webm;codecs=opus", "kn"]);
});

test("a silent clip is never uploaded, and asks again", async () => {
  removeRecognition();
  clipOk = false;
  const transcribe = vi.fn();
  const onText = vi.fn();
  withServices({ transcribe }, <VoiceInput lang="kn" onText={onText} />);
  await userEvent.click(screen.getByRole("button", { name: "ಒತ್ತಿ ಮಾತನಾಡಿ" }));
  await userEvent.click(await screen.findByRole("button", { name: "ನಿಲ್ಲಿಸಲು ಒತ್ತಿ" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("ಕೇಳಿಸಲಿಲ್ಲ");
  expect(transcribe).not.toHaveBeenCalled();
  expect(onText).not.toHaveBeenCalled();
});

test("a server transcription failure counts as not heard", async () => {
  removeRecognition();
  const transcribe = vi.fn(async () => {
    throw new Error("503");
  });
  const onNotHeard = vi.fn();
  withServices({ transcribe }, <VoiceInput lang="kn" onText={() => {}} onNotHeard={onNotHeard} />);
  await userEvent.click(screen.getByRole("button", { name: "ಒತ್ತಿ ಮಾತನಾಡಿ" }));
  await userEvent.click(await screen.findByRole("button", { name: "ನಿಲ್ಲಿಸಲು ಒತ್ತಿ" }));
  await waitFor(() => expect(onNotHeard).toHaveBeenCalledWith(1));
});
