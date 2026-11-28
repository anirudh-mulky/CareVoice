/**
 * Server speech for real mode (Part 12). When the backend has a real STT/TTS provider, the
 * voice components use it (Indian-language voices that phones often lack); otherwise, or if
 * a call fails, they fall back to the browser's own speech exactly as in demo mode.
 */
import { useQuery } from "@tanstack/react-query";
import { createContext, useContext } from "react";
import { getSystemStatus } from "./api/client";
import type { Transcript } from "./speech";

export type VoiceServices = {
  /** Recording -> text, via POST /api/v1/voice/transcribe. */
  transcribe?: (audio: Blob, mimeType: string, lang: string) => Promise<Transcript>;
  /** Text -> MP3, via the patient link (cached on the server). */
  speak?: (text: string, lang: string) => Promise<Blob>;
};

export const VoiceServicesContext = createContext<VoiceServices>({});

export const useVoiceServices = () => useContext(VoiceServicesContext);

export async function transcribeOnServer(audio: Blob, mimeType: string, lang: string): Promise<Transcript> {
  const res = await globalThis.fetch(`/api/v1/voice/transcribe?lang=${encodeURIComponent(lang)}`, {
    method: "POST",
    headers: { "content-type": mimeType || "audio/webm" },
    body: audio,
  });
  if (!res.ok) throw new Error(`transcribe failed: ${res.status}`);
  const data = (await res.json()) as { text: string; language: string; confidence: number | null };
  return { text: data.text, language: data.language, confidence: data.confidence };
}

export function speakOnServer(token: string) {
  return async (text: string, lang: string): Promise<Blob> => {
    const res = await globalThis.fetch(`/api/v1/patient/${token}/speak`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text, language: lang }),
    });
    if (!res.ok) throw new Error(`speak failed: ${res.status}`);
    return res.blob();
  };
}

/** Which server speech the backend offers (real mode with keys). */
export function useServerSpeech() {
  const status = useQuery({ queryKey: ["system-status"], queryFn: getSystemStatus, staleTime: 60_000 });
  const real = (kind: string) => status.data?.providers.some((p) => p.kind === kind && p.mode === "real") ?? false;
  return { stt: real("stt"), tts: real("tts") };
}

