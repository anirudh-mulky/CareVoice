import { checkClip, LevelMeter, MAX_DURATION_MS, MIN_DURATION_MS, MIN_RMS, rms } from "./clip";

describe("rms", () => {
  test("silence is zero", () => {
    expect(rms(new Float32Array(1024))).toBe(0);
    expect(rms([])).toBe(0);
  });
  test("a full-scale square wave is 1", () => {
    expect(rms([1, -1, 1, -1])).toBeCloseTo(1);
  });
  test("a sine wave of amplitude 0.5 is about 0.354", () => {
    const sine = Array.from({ length: 1000 }, (_, i) => 0.5 * Math.sin((2 * Math.PI * i) / 100));
    expect(rms(sine)).toBeCloseTo(0.354, 2);
  });
});

describe("LevelMeter", () => {
  test("keeps the loudest frame", () => {
    const meter = new LevelMeter();
    meter.push([0.01, -0.01]);
    meter.push([0.3, -0.3]);
    meter.push([0.02, -0.02]);
    expect(meter.peak).toBeCloseTo(0.3);
    expect(meter.frames).toBe(3);
  });
});

describe("checkClip", () => {
  test("rejects clips under one second", () => {
    expect(checkClip(MIN_DURATION_MS - 1, 0.2)).toEqual({ ok: false, problem: "too_short" });
    expect(checkClip(300, 0.2)).toEqual({ ok: false, problem: "too_short" });
  });
  test("rejects near-silent clips", () => {
    expect(checkClip(3000, MIN_RMS - 0.001)).toEqual({ ok: false, problem: "silent" });
    expect(checkClip(3000, 0)).toEqual({ ok: false, problem: "silent" });
  });
  test("too short is reported before silent", () => {
    expect(checkClip(200, 0)).toEqual({ ok: false, problem: "too_short" });
  });
  test("accepts a one-second clip with speech", () => {
    expect(checkClip(MIN_DURATION_MS, MIN_RMS)).toEqual({ ok: true });
    expect(checkClip(5000, 0.08)).toEqual({ ok: true });
  });
  test("rejects garbage measurements", () => {
    expect(checkClip(Number.NaN, 0.2).ok).toBe(false);
    expect(checkClip(2000, Number.NaN).ok).toBe(false);
  });
  test("the recording cap is 60 seconds", () => {
    expect(MAX_DURATION_MS).toBe(60_000);
  });
});
