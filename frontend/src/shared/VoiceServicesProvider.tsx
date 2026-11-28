import { type ReactNode, useMemo } from "react";
import {
  speakOnServer,
  transcribeOnServer,
  useServerSpeech,
  type VoiceServices,
  VoiceServicesContext,
} from "./voiceServices";

/** Patient pages: server speech-to-text and text-to-speech (speech needs their link token). */
export function VoiceServicesProvider({ token, children }: { token?: string; children: ReactNode }) {
  const server = useServerSpeech();
  const value = useMemo<VoiceServices>(
    () => ({
      transcribe: server.stt ? transcribeOnServer : undefined,
      speak: server.tts && token ? speakOnServer(token) : undefined,
    }),
    [server.stt, server.tts, token],
  );
  return <VoiceServicesContext.Provider value={value}>{children}</VoiceServicesContext.Provider>;
}
