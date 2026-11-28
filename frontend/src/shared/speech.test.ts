import { afterEach } from "vitest";
import { installRecognition, installSynthesis, removeRecognition, removeSynthesis, voice } from "@/test/fakeSpeech";
import { speechCode } from "./languages";
import { isRecognitionSupported, pickVoice, recognize, SpeechError, sentences, speak } from "./speech";

afterEach(() => {
  removeRecognition();
  removeSynthesis();
  vi.unstubAllGlobals();
});

test("language codes map to Indian locales", () => {
  expect(speechCode("kn")).toBe("kn-IN");
  expect(speechCode("hi")).toBe("hi-IN");
  expect(speechCode("ta-IN")).toBe("ta-IN");
  expect(speechCode("xx")).toBe("en-IN");
});

describe("recognize", () => {
  test("unsupported browsers reject with a clear code", async () => {
    removeRecognition();
    expect(isRecognitionSupported()).toBe(false);
    await expect(recognize({ lang: "kn" }).result).rejects.toMatchObject({ code: "unsupported" });
  });

  test("returns the Kannada transcript with the right locale and confidence", async () => {
    installRecognition([
      { kind: "result", text: "kannu tumba kempagide", confidence: 0.8 },
      { kind: "result", text: "novu ide", confidence: 0.6 },
    ]);
    const interims: string[] = [];
    const session = recognize({ lang: "kn", onInterim: (t) => interims.push(t) });
    session.stop();
    const result = await session.result;
    expect(result).toEqual({ text: "kannu tumba kempagide novu ide", language: "kn-IN", confidence: 0.7 });
    expect(interims.at(-1)).toBe("kannu tumba kempagide novu ide");
  });

  test("hearing nothing resolves to empty text, not an error", async () => {
    installRecognition([{ kind: "error", error: "no-speech" }]);
    const session = recognize({ lang: "ta" });
    session.stop();
    expect((await session.result).text).toBe("");
  });

  test("a blocked microphone rejects with not-allowed", async () => {
    installRecognition([{ kind: "error", error: "not-allowed" }]);
    const session = recognize({ lang: "hi" });
    session.stop();
    await expect(session.result).rejects.toBeInstanceOf(SpeechError);
  });

  test("missing confidence is reported as null", async () => {
    installRecognition([{ kind: "result", text: "hello", confidence: 0 }]);
    const session = recognize({ lang: "en" });
    session.stop();
    expect((await session.result).confidence).toBeNull();
  });
});

describe("speech synthesis", () => {
  test("picks the exact locale, then the language", () => {
    const voices = [voice("en-US"), voice("hi-IN"), voice("ta_IN"), voice("kn-IN")];
    expect(pickVoice(voices, "kn")?.lang).toBe("kn-IN");
    expect(pickVoice(voices, "ta")?.lang).toBe("ta_IN");
    expect(pickVoice([voice("hi-XX")], "hi")?.lang).toBe("hi-XX");
    expect(pickVoice([voice("en-US")], "kn")).toBeNull();
  });

  test("splits long text into sentences, including the Devanagari full stop", () => {
    expect(sentences("Put drops. Is it red? Tap the mic!")).toEqual(["Put drops.", "Is it red?", "Tap the mic!"]);
    expect(sentences("कल जाँच है। कृपया आएँ।")).toEqual(["कल जाँच है।", "कृपया आएँ।"]);
  });

  test("speaks each sentence with the language's voice", async () => {
    const spoken = installSynthesis([voice("en-US"), voice("kn-IN", "Kannada")]);
    const result = await speak("ಮೊದಲ ವಾಕ್ಯ. ಎರಡನೇ ವಾಕ್ಯ.", "kn");
    expect(result).toEqual({ spoken: true });
    expect(spoken).toEqual([
      { text: "ಮೊದಲ ವಾಕ್ಯ.", lang: "kn-IN", voice: "Kannada" },
      { text: "ಎರಡನೇ ವಾಕ್ಯ.", lang: "kn-IN", voice: "Kannada" },
    ]);
  });

  test("never reads Kannada with an English voice", async () => {
    const spoken = installSynthesis([voice("en-US")]);
    expect(await speak("ನಮಸ್ಕಾರ", "kn")).toEqual({ spoken: false, reason: "no_voice" });
    expect(spoken).toEqual([]);
  });

  test("reports unsupported browsers", async () => {
    removeSynthesis();
    expect(await speak("hello", "en")).toEqual({ spoken: false, reason: "unsupported" });
  });
});
