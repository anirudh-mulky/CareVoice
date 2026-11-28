/**
 * One voice interaction: tap to listen, tap to stop (or 60 s / silence), then either a
 * transcript or a "couldn't hear you" retry. Records audio alongside browser recognition
 * so a too-short or silent clip is caught before anything is sent.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { MessageKey } from "./i18n";
import { MAX_DURATION_MS } from "./clip";
import { Recorder, RecorderError, type Recording, isRecordingSupported } from "./Recorder";
import { isRecognitionSupported, type RecognitionSession, recognize, SpeechError, type Transcript } from "./speech";
import { useVoiceServices } from "./voiceServices";

export type CaptureStatus = "idle" | "listening" | "processing";

export type CaptureResult = Transcript & { recording: Recording | null };

export type VoiceCaptureOptions = {
  lang: string;
  onResult: (result: CaptureResult) => void;
  /** Called after each failed attempt with the running count (Part 11: icons after 2). */
  onNotHeard?: (failures: number) => void;
  /** Record audio for the clip check (and upload in real mode). Default true. */
  record?: boolean;
  maxMs?: number;
  /** Below this speech-recognition confidence, ask once to say it again (noisy room). */
  minConfidence?: number;
};

/** Same threshold as the backend's STT_CONFIDENCE_ALERT_THRESHOLD. */
export const LOW_CONFIDENCE = 0.6;

export function useVoiceCapture({
  lang,
  onResult,
  onNotHeard,
  record = true,
  maxMs = MAX_DURATION_MS,
  minConfidence,
}: VoiceCaptureOptions) {
  const [status, setStatus] = useState<CaptureStatus>("idle");
  const [interim, setInterim] = useState("");
  const [level, setLevel] = useState(0);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [message, setMessage] = useState<MessageKey | null>(null);
  const [failures, setFailures] = useState(0);

  const session = useRef<RecognitionSession | null>(null);
  const recorder = useRef<Recorder | null>(null);
  const finishing = useRef(false);
  // One "please say it again" for a low-confidence result; the next one goes through and the
  // server escalates it to the doctor (never guess on unclear speech).
  const lowConfidenceRetried = useRef(false);
  const callbacks = useRef({ onResult, onNotHeard });
  useEffect(() => {
    callbacks.current = { onResult, onNotHeard };
  });

  const services = useVoiceServices();
  // Real mode: record, then the server transcribes (no browser recognition needed).
  const serverStt = Boolean(services.transcribe) && isRecordingSupported();
  const usingServer = useRef(false);
  const supported = serverStt || isRecognitionSupported();

  const notHeard = useCallback(() => {
    setMessage("mic.not_heard");
    setFailures((n) => {
      callbacks.current.onNotHeard?.(n + 1);
      return n + 1;
    });
  }, []);

  const finish = useCallback(async () => {
    if (finishing.current) return;
    finishing.current = true;
    setStatus("processing");
    session.current?.stop();
    let recording: Recording | null = null;
    let transcript: Transcript | null = null;
    let failure: unknown = null;
    try {
      recording = recorder.current ? await recorder.current.stop() : null;
      if (usingServer.current) {
        // A too-short or silent clip is never uploaded.
        transcript =
          recording && recording.check.ok && services.transcribe
            ? await services.transcribe(recording.blob, recording.mimeType, lang)
            : null;
      } else {
        transcript = session.current ? await session.current.result : null;
      }
    } catch (err) {
      failure = err;
    }
    session.current = null;
    recorder.current = null;
    setInterim("");
    setStatus("idle");

    if (failure instanceof SpeechError && failure.code === "not-allowed") {
      setMessage("mic.permission_denied");
      return;
    }
    if (failure || !transcript || (recording && !recording.check.ok) || !transcript.text.trim()) {
      notHeard();
      return;
    }
    const unsure = minConfidence !== undefined && transcript.confidence !== null && transcript.confidence < minConfidence;
    if (unsure && !lowConfidenceRetried.current) {
      lowConfidenceRetried.current = true;
      notHeard();
      return;
    }
    lowConfidenceRetried.current = false;
    setMessage(null);
    setFailures(0);
    callbacks.current.onResult({ ...transcript, recording });
  }, [notHeard, minConfidence, services, lang]);

  const start = useCallback(async () => {
    if (status !== "idle") return;
    setMessage(null);
    if (!supported) {
      setMessage("mic.unsupported");
      return;
    }
    finishing.current = false;
    setStatus("listening");
    setElapsedMs(0);
    usingServer.current = false;

    if (serverStt) {
      const rec = new Recorder({ maxMs, onLevel: setLevel, onAutoStop: () => void finish() });
      try {
        await rec.start();
        recorder.current = rec;
        usingServer.current = true;
        return; // tap again (or the 60 s limit) to stop and transcribe
      } catch (err) {
        if (err instanceof RecorderError && err.code === "not-allowed") {
          setStatus("idle");
          setMessage("mic.permission_denied");
          return;
        }
        if (!isRecognitionSupported()) {
          setStatus("idle");
          setMessage("mic.unsupported");
          return;
        }
        // No recorder here: browser recognition below still works.
      }
    }

    if (record && isRecordingSupported()) {
      const rec = new Recorder({ maxMs, onLevel: setLevel, onAutoStop: () => void finish() });
      try {
        await rec.start();
        recorder.current = rec;
      } catch (err) {
        if (err instanceof RecorderError && err.code === "not-allowed") {
          setStatus("idle");
          setMessage("mic.permission_denied");
          return;
        }
        // No recorder (e.g. no device access for MediaRecorder): recognition alone still works.
      }
    }

    const s = recognize({ lang, onInterim: setInterim });
    session.current = s;
    // Recognition can end by itself (silence, or one utterance on Android): finish then.
    s.result.then(
      () => void finish(),
      () => void finish(),
    );
  }, [status, supported, serverStt, record, maxMs, lang, finish]);

  const stop = useCallback(() => void finish(), [finish]);

  const toggle = useCallback(() => {
    if (status === "idle") void start();
    else if (status === "listening") stop();
  }, [status, start, stop]);

  // Elapsed timer for the "seconds left" hint.
  useEffect(() => {
    if (status !== "listening") return;
    const startedAt = performance.now();
    const id = setInterval(() => setElapsedMs(performance.now() - startedAt), 250);
    return () => clearInterval(id);
  }, [status]);

  // Release the mic if the component unmounts mid-recording.
  useEffect(
    () => () => {
      session.current?.abort();
      recorder.current?.cancel();
    },
    [],
  );

  return {
    status,
    interim,
    level,
    secondsLeft: Math.max(0, Math.ceil((maxMs - elapsedMs) / 1000)),
    message,
    failures,
    supported,
    start,
    stop,
    toggle,
    clearMessage: () => setMessage(null),
  };
}
