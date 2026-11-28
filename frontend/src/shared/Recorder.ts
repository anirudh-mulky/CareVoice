/**
 * Microphone recorder: MediaRecorder (webm/opus, mono), browser noise suppression and
 * echo cancellation on, 60 s cap, and a live level meter for the clip check.
 */

import { type ClipCheck, checkClip, LevelMeter, MAX_DURATION_MS } from "./clip";

export type Recording = {
  blob: Blob;
  mimeType: string;
  durationMs: number;
  peakRms: number;
  check: ClipCheck;
};

export type RecorderErrorCode = "unsupported" | "not-allowed" | "no-device" | "unknown";

export class RecorderError extends Error {
  constructor(public readonly code: RecorderErrorCode, message?: string) {
    super(message ?? code);
  }
}

export const AUDIO_CONSTRAINTS: MediaTrackConstraints = {
  channelCount: 1,
  sampleRate: 16000,
  echoCancellation: true,
  noiseSuppression: true,
  autoGainControl: true,
};

const PREFERRED_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];

export function isRecordingSupported(): boolean {
  return (
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof window !== "undefined" &&
    "MediaRecorder" in window
  );
}

function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return undefined;
  return PREFERRED_TYPES.find((t) => MediaRecorder.isTypeSupported(t));
}

export class Recorder {
  private stream: MediaStream | null = null;
  private recorder: MediaRecorder | null = null;
  private context: AudioContext | null = null;
  private chunks: Blob[] = [];
  private meter = new LevelMeter();
  private startedAt = 0;
  private frame = 0;
  private capTimer: ReturnType<typeof setTimeout> | null = null;
  private stopped: Promise<Recording> | null = null;

  constructor(
    private readonly options: {
      maxMs?: number;
      onLevel?: (level: number) => void;
      onAutoStop?: () => void;
    } = {},
  ) {}

  get recording(): boolean {
    return this.recorder?.state === "recording";
  }

  get elapsedMs(): number {
    return this.startedAt ? performance.now() - this.startedAt : 0;
  }

  async start(): Promise<void> {
    if (!isRecordingSupported()) throw new RecorderError("unsupported");
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: AUDIO_CONSTRAINTS });
    } catch (err) {
      const name = err instanceof DOMException ? err.name : "";
      if (name === "NotAllowedError" || name === "SecurityError") throw new RecorderError("not-allowed");
      if (name === "NotFoundError" || name === "OverconstrainedError") throw new RecorderError("no-device");
      throw new RecorderError("unknown", String(err));
    }

    const mimeType = pickMimeType();
    this.recorder = new MediaRecorder(this.stream, mimeType ? { mimeType } : undefined);
    this.chunks = [];
    this.recorder.ondataavailable = (e) => {
      if (e.data.size > 0) this.chunks.push(e.data);
    };
    this.startMeter(this.stream);
    this.recorder.start(250);
    this.startedAt = performance.now();
    this.capTimer = setTimeout(() => {
      this.options.onAutoStop?.();
      void this.stop();
    }, this.options.maxMs ?? MAX_DURATION_MS);
  }

  private startMeter(stream: MediaStream): void {
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    this.context = new Ctx();
    const analyser = this.context.createAnalyser();
    analyser.fftSize = 1024;
    this.context.createMediaStreamSource(stream).connect(analyser);
    const buffer = new Float32Array(analyser.fftSize);
    const tick = () => {
      analyser.getFloatTimeDomainData(buffer);
      const level = this.meter.push(buffer);
      this.options.onLevel?.(Math.min(1, level * 8));
      this.frame = requestAnimationFrame(tick);
    };
    this.frame = requestAnimationFrame(tick);
  }

  /** Stop and return the clip with its check result. Safe to call more than once. */
  stop(): Promise<Recording> {
    if (this.stopped) return this.stopped;
    const recorder = this.recorder;
    const durationMs = this.elapsedMs;
    this.stopped = new Promise<Recording>((resolve) => {
      const finish = () => {
        const mimeType = recorder?.mimeType || "audio/webm";
        const blob = new Blob(this.chunks, { type: mimeType });
        const peakRms = this.meter.peak;
        this.cleanup();
        resolve({ blob, mimeType, durationMs, peakRms, check: checkClip(durationMs, peakRms) });
      };
      if (recorder && recorder.state !== "inactive") {
        recorder.onstop = finish;
        recorder.stop();
      } else {
        finish();
      }
    });
    return this.stopped;
  }

  cancel(): void {
    if (this.recorder && this.recorder.state !== "inactive") {
      this.recorder.onstop = null;
      this.recorder.stop();
    }
    this.cleanup();
  }

  private cleanup(): void {
    if (this.capTimer) clearTimeout(this.capTimer);
    cancelAnimationFrame(this.frame);
    this.stream?.getTracks().forEach((t) => t.stop());
    void this.context?.close().catch(() => {});
    this.stream = null;
    this.context = null;
    this.options.onLevel?.(0);
  }
}
