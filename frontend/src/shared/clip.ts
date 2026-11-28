/**
 * Client-side clip check (spec: "Capture"): reject clips under 1 s or with near-zero
 * energy before anything is uploaded, and ask the patient to say it again.
 */

export const MIN_DURATION_MS = 1000;
export const MAX_DURATION_MS = 60_000;
/** RMS of normalised samples (-1..1). Quiet speech near a phone is ~0.02-0.1; silence < 0.005. */
export const MIN_RMS = 0.01;

export type ClipProblem = "too_short" | "silent";
export type ClipCheck = { ok: true } | { ok: false; problem: ClipProblem };

/** Root mean square of a block of samples. */
export function rms(samples: ArrayLike<number>): number {
  if (samples.length === 0) return 0;
  let sum = 0;
  for (let i = 0; i < samples.length; i++) {
    const s = samples[i] ?? 0;
    sum += s * s;
  }
  return Math.sqrt(sum / samples.length);
}

/** Running loudness of a recording: keeps the peak of per-frame RMS values. */
export class LevelMeter {
  peak = 0;
  frames = 0;

  push(samples: ArrayLike<number>): number {
    const level = rms(samples);
    this.peak = Math.max(this.peak, level);
    this.frames += 1;
    return level;
  }
}

export function checkClip(durationMs: number, peakRms: number): ClipCheck {
  if (!Number.isFinite(durationMs) || durationMs < MIN_DURATION_MS) {
    return { ok: false, problem: "too_short" };
  }
  if (!Number.isFinite(peakRms) || peakRms < MIN_RMS) return { ok: false, problem: "silent" };
  return { ok: true };
}
