/** Test doubles for the Web Speech API (jsdom has none). */
import { vi } from "vitest";
import type { SpeechRecognitionLike } from "@/shared/speech";

type Script =
  | { kind: "result"; text: string; confidence?: number; isFinal?: boolean }
  | { kind: "error"; error: string };

export class FakeRecognition implements SpeechRecognitionLike {
  static instances: FakeRecognition[] = [];
  static script: Script[] = [];
  lang = "";
  continuous = false;
  interimResults = false;
  maxAlternatives = 1;
  onresult: SpeechRecognitionLike["onresult"] = null;
  onerror: SpeechRecognitionLike["onerror"] = null;
  onend: SpeechRecognitionLike["onend"] = null;
  started = false;

  constructor() {
    FakeRecognition.instances.push(this);
  }
  start() {
    this.started = true;
  }
  /** Emit the scripted events, then end, as Chrome does after stop(). */
  stop() {
    const results: { isFinal: boolean; length: number; 0: { transcript: string; confidence: number } }[] = [];
    for (const step of FakeRecognition.script) {
      if (step.kind === "error") {
        this.onerror?.({ error: step.error });
      } else {
        results.push({ isFinal: step.isFinal ?? true, length: 1, 0: { transcript: step.text, confidence: step.confidence ?? 0.9 } });
        this.onresult?.({ resultIndex: results.length - 1, results: Object.assign([...results], { length: results.length }) });
      }
    }
    this.onend?.();
  }
  abort() {
    this.onerror?.({ error: "aborted" });
    this.onend?.();
  }
}

export function installRecognition(script: Script[]) {
  FakeRecognition.instances = [];
  FakeRecognition.script = script;
  vi.stubGlobal("SpeechRecognition", FakeRecognition);
  (window as unknown as { SpeechRecognition: unknown }).SpeechRecognition = FakeRecognition;
}

export function removeRecognition() {
  delete (window as unknown as { SpeechRecognition?: unknown }).SpeechRecognition;
  delete (window as unknown as { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition;
}

export function voice(lang: string, name = `Voice ${lang}`): SpeechSynthesisVoice {
  return { lang, name, default: false, localService: true, voiceURI: name } as SpeechSynthesisVoice;
}

export function installSynthesis(voices: SpeechSynthesisVoice[]) {
  const spoken: { text: string; lang: string; voice: string | undefined }[] = [];
  class Utterance {
    voice: SpeechSynthesisVoice | null = null;
    lang = "";
    rate = 1;
    onend: (() => void) | null = null;
    onerror: ((e: { error: string }) => void) | null = null;
    constructor(public text: string) {}
  }
  const synth = {
    getVoices: () => voices,
    speak: (u: Utterance) => {
      spoken.push({ text: u.text, lang: u.lang, voice: u.voice?.name });
      queueMicrotask(() => u.onend?.());
    },
    cancel: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  };
  vi.stubGlobal("SpeechSynthesisUtterance", Utterance);
  Object.defineProperty(window, "speechSynthesis", { value: synth, configurable: true });
  return spoken;
}

export function removeSynthesis() {
  delete (window as unknown as { speechSynthesis?: unknown }).speechSynthesis;
}
