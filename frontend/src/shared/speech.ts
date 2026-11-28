/**
 * Browser speech (demo mode): Web Speech API recognition and speechSynthesis.
 * Works with no keys in Chrome on localhost or HTTPS. Real mode swaps in server-side
 * STT/TTS behind the same calls; every screen also offers "type instead".
 */

import { speechCode } from "./languages";

// --- Recognition (speech to text) -------------------------------------------

export type Transcript = {
  text: string;
  language: string;
  /** 0..1, or null when the browser does not report it. */
  confidence: number | null;
};

export type SpeechErrorCode =
  | "unsupported"
  | "not-allowed"
  | "audio-capture"
  | "network"
  | "aborted"
  | "unknown";

export class SpeechError extends Error {
  constructor(public readonly code: SpeechErrorCode, message?: string) {
    super(message ?? code);
  }
}

// Minimal Web Speech API types (not in TypeScript's DOM lib).
type RecognitionAlternative = { transcript: string; confidence: number };
type RecognitionResult = { isFinal: boolean; length: number; [index: number]: RecognitionAlternative };
type RecognitionEvent = { resultIndex: number; results: { length: number; [index: number]: RecognitionResult } };
type RecognitionErrorEvent = { error: string; message?: string };
export interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: RecognitionEvent) => void) | null;
  onerror: ((event: RecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
type RecognitionCtor = new () => SpeechRecognitionLike;

function recognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function isRecognitionSupported(): boolean {
  return recognitionCtor() !== null;
}

function isAndroid(): boolean {
  return typeof navigator !== "undefined" && /Android/i.test(navigator.userAgent);
}

const ERROR_CODES: Record<string, SpeechErrorCode> = {
  "not-allowed": "not-allowed",
  "service-not-allowed": "not-allowed",
  "audio-capture": "audio-capture",
  network: "network",
  aborted: "aborted",
};

export type RecognitionSession = {
  /** Resolves when listening ends; an empty text means nothing was heard. */
  result: Promise<Transcript>;
  /** Stop listening and keep what was heard. */
  stop: () => void;
  /** Stop listening and discard. */
  abort: () => void;
};

export function recognize(options: {
  lang: string;
  onInterim?: (text: string) => void;
  continuous?: boolean;
}): RecognitionSession {
  const Ctor = recognitionCtor();
  if (!Ctor) {
    return {
      result: Promise.reject(new SpeechError("unsupported")),
      stop: () => {},
      abort: () => {},
    };
  }
  const recognition = new Ctor();
  const language = speechCode(options.lang);
  recognition.lang = language;
  // Continuous mode repeats words on Android Chrome; there, one utterance per tap.
  recognition.continuous = options.continuous ?? !isAndroid();
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;

  const finals: RecognitionAlternative[] = [];
  let interim = "";
  let failure: SpeechError | null = null;

  const result = new Promise<Transcript>((resolve, reject) => {
    recognition.onresult = (event) => {
      interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const res = event.results[i];
        const best = res?.[0];
        if (!res || !best) continue;
        if (res.isFinal) finals.push(best);
        else interim += best.transcript;
      }
      options.onInterim?.(joined(finals.map((f) => f.transcript), interim));
    };
    recognition.onerror = (event) => {
      if (event.error === "no-speech") return; // ends with empty text: "couldn't hear you"
      failure = new SpeechError(ERROR_CODES[event.error] ?? "unknown", event.message);
    };
    recognition.onend = () => {
      if (failure && failure.code !== "aborted") return reject(failure);
      if (failure) return resolve({ text: "", language, confidence: null });
      const text = joined(finals.map((f) => f.transcript), interim);
      const scores = finals.map((f) => f.confidence).filter((c) => c > 0);
      const confidence = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
      resolve({ text, language, confidence });
    };
  });

  try {
    recognition.start();
  } catch (err) {
    return { result: Promise.reject(new SpeechError("unknown", String(err))), stop: () => {}, abort: () => {} };
  }
  return { result, stop: () => recognition.stop(), abort: () => recognition.abort() };
}

function joined(parts: string[], tail: string): string {
  return [...parts, tail].map((p) => p.trim()).filter(Boolean).join(" ");
}

// --- Synthesis (text to speech) ---------------------------------------------

export function isSynthesisSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

/** Voices load asynchronously in Chrome; wait briefly for them. */
export async function loadVoices(timeoutMs = 1500): Promise<SpeechSynthesisVoice[]> {
  if (!isSynthesisSupported()) return [];
  const synth = window.speechSynthesis;
  const now = synth.getVoices();
  if (now.length) return now;
  return new Promise((resolve) => {
    const done = () => {
      synth.removeEventListener?.("voiceschanged", done);
      clearTimeout(timer);
      resolve(synth.getVoices());
    };
    const timer = setTimeout(done, timeoutMs);
    synth.addEventListener?.("voiceschanged", done);
  });
}

/** Best voice for a language: exact "kn-IN", then any "kn-*". Null if the device has none. */
export function pickVoice(voices: SpeechSynthesisVoice[], lang: string): SpeechSynthesisVoice | null {
  const code = speechCode(lang).toLowerCase();
  const base = code.split("-")[0] ?? code;
  const norm = (v: SpeechSynthesisVoice) => v.lang.replace("_", "-").toLowerCase();
  return (
    voices.find((v) => norm(v) === code) ??
    voices.find((v) => norm(v).split("-")[0] === base) ??
    null
  );
}

/** Split long text into sentences: Chrome cuts off utterances longer than ~15 seconds. */
export function sentences(text: string): string[] {
  return text
    .split(/(?<=[.!?।])\s+|\n+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export type SpeakResult =
  | { spoken: true }
  | { spoken: false; reason: "unsupported" | "no_voice" | "stopped" | "error" };

/**
 * Speak text in a language. Resolves when finished. Never speaks Kannada with an English
 * voice: if the device has no voice for the language it returns no_voice so the UI can
 * ask the patient to read instead.
 */
export async function speak(
  text: string,
  lang: string,
  options: { rate?: number; onStart?: () => void } = {},
): Promise<SpeakResult> {
  if (!isSynthesisSupported()) return { spoken: false, reason: "unsupported" };
  const synth = window.speechSynthesis;
  const voice = pickVoice(await loadVoices(), lang);
  if (!voice) return { spoken: false, reason: "no_voice" };

  synth.cancel();
  const parts = sentences(text);
  options.onStart?.();
  for (const part of parts) {
    const outcome = await new Promise<"done" | "stopped" | "error">((resolve) => {
      const utterance = new SpeechSynthesisUtterance(part);
      utterance.voice = voice;
      utterance.lang = voice.lang;
      utterance.rate = options.rate ?? 0.9; // a little slower for elderly patients
      utterance.onend = () => resolve("done");
      utterance.onerror = (e) =>
        resolve(e.error === "interrupted" || e.error === "canceled" ? "stopped" : "error");
      synth.speak(utterance);
    });
    if (outcome !== "done") return { spoken: false, reason: outcome };
  }
  return { spoken: true };
}

export function stopSpeaking(): void {
  if (isSynthesisSupported()) window.speechSynthesis.cancel();
}
