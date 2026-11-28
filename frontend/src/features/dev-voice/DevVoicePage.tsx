import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { getSystemStatus } from "@/shared/api/client";
import { AudioPlayer } from "@/shared/AudioPlayer";
import { useI18n } from "@/shared/i18n";
import { LANG_CODES, LANGUAGES, type Lang, speechCode } from "@/shared/languages";
import { cn } from "@/shared/lib/utils";
import { isRecordingSupported } from "@/shared/Recorder";
import { isRecognitionSupported, isSynthesisSupported, loadVoices, pickVoice } from "@/shared/speech";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import type { CaptureResult } from "@/shared/useVoiceCapture";
import { VoiceInput } from "@/shared/VoiceInput";

const SAMPLES: Record<Lang, string> = {
  en: "Please put your eye drops now. If your eye is red or painful, tap the mic and tell me.",
  kn: "ಕಣ್ಣಿನ ಹನಿ ಹಾಕುವ ಸಮಯ. ನಿಮ್ಮ ಕಣ್ಣು ಕೆಂಪಾಗಿದೆಯೇ ಅಥವಾ ನೋವಿದೆಯೇ? ಮೈಕ್ ಒತ್ತಿ ಹೇಳಿ.",
  hi: "आपके टांके कैसे हैं? अगर लाल हैं, रिस रहे हैं या बहुत दर्द है, तो माइक दबाकर बताएँ।",
  ta: "கண் சொட்டு மருந்து நேரம். உங்கள் கண் சிவப்பாக அல்லது வலியாக உள்ளதா? மைக்கைத் தட்டிச் சொல்லுங்கள்.",
};

type Heard = { text: string; typed: boolean; result?: CaptureResult; at: Date };

function Check({ ok, children }: { ok: boolean; children: ReactNode }) {
  return (
    <li className="flex items-center gap-2 text-sm">
      {ok ? (
        <CheckCircle2 className="size-4 text-primary" aria-label="yes" />
      ) : (
        <XCircle className="size-4 text-destructive" aria-label="no" />
      )}
      {children}
    </li>
  );
}

function SpeakBack({ lang }: { lang: Lang }) {
  const [sample, setSample] = useState(SAMPLES[lang]);
  return (
    <div className="flex flex-col gap-3">
      <textarea
        value={sample}
        onChange={(e) => setSample(e.target.value)}
        lang={lang}
        rows={3}
        aria-label="Text to speak"
        className="w-full rounded-md border bg-background px-3 py-2 text-base"
      />
      <AudioPlayer text={sample} lang={lang} />
    </div>
  );
}

/** Hidden page (not linked anywhere) to try the shared voice pieces in each language. */
export function DevVoicePage() {
  const { lang, setLang } = useI18n();
  const [heard, setHeard] = useState<Heard[]>([]);
  const [failures, setFailures] = useState(0);
  const status = useQuery({ queryKey: ["system-status"], queryFn: getSystemStatus });
  const voice = useQuery({
    queryKey: ["voice", lang],
    queryFn: async () => pickVoice(await loadVoices(), lang)?.name ?? null,
  });
  const voiceName = voice.isPending ? undefined : (voice.data ?? null);

  const last = heard[0];
  const recordingUrl = last?.result?.recording ? URL.createObjectURL(last.result.recording.blob) : null;
  useEffect(() => () => void (recordingUrl && URL.revokeObjectURL(recordingUrl)), [recordingUrl]);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 py-8">
      <div>
        <Badge variant="outline">Developer page</Badge>
        <h1 className="mt-2 text-2xl font-semibold">Voice check</h1>
        <p className="text-muted-foreground">
          Try the shared mic, recorder, browser speech and type-instead box. Use Chrome on localhost or HTTPS.
        </p>
      </div>

      <div role="radiogroup" aria-label="Language" className="flex flex-wrap gap-2">
        {LANG_CODES.map((code) => (
          <button
            key={code}
            type="button"
            role="radio"
            aria-checked={lang === code}
            onClick={() => setLang(code)}
            className={cn(
              "rounded-full border px-4 py-2 text-sm font-medium transition-colors",
              lang === code ? "border-primary bg-primary text-primary-foreground" : "hover:bg-accent",
            )}
          >
            {LANGUAGES[code].label} <span className="opacity-60">{speechCode(code)}</span>
          </button>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>This browser</CardTitle>
          <CardDescription>What voice features are available here.</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="grid gap-1.5 sm:grid-cols-2">
            <Check ok={isRecognitionSupported()}>Speech recognition</Check>
            <Check ok={isSynthesisSupported()}>Speech synthesis</Check>
            <Check ok={isRecordingSupported()}>Microphone recording</Check>
            <Check ok={!!voiceName}>
              {voiceName === undefined
                ? "Checking voices…"
                : voiceName
                  ? `Voice for ${LANGUAGES[lang].label}: ${voiceName}`
                  : `No voice for ${LANGUAGES[lang].label} on this device`}
            </Check>
          </ul>
          {status.data && (
            <p className="mt-3 text-sm text-muted-foreground">
              Server: {status.data.mode} mode ·{" "}
              {status.data.providers.map((p) => `${p.kind} ${p.active}`).join(" · ")}
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>1. Speak</CardTitle>
          <CardDescription>Tap the mic, speak in {LANGUAGES[lang].label}, tap again. Or type instead.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <VoiceInput
            key={lang}
            lang={lang}
            onNotHeard={setFailures}
            onText={(text, details) => {
              setFailures(0);
              setHeard((h) => [{ text, ...details, at: new Date() }, ...h].slice(0, 5));
            }}
          />
          <p className="text-center text-sm text-muted-foreground">Failed attempts in a row: {failures}</p>
          {last && (
            <div className="rounded-lg border bg-muted/40 p-4">
              <p className="text-sm text-muted-foreground">{last.typed ? "Typed" : "Heard"}</p>
              <p lang={lang} className="text-xl" data-testid="transcript">
                {last.text}
              </p>
              {last.result && (
                <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-4">
                  <dt className="text-muted-foreground">Language</dt>
                  <dd>{last.result.language}</dd>
                  <dt className="text-muted-foreground">Confidence</dt>
                  <dd>{last.result.confidence?.toFixed(2) ?? "not reported"}</dd>
                  {last.result.recording && (
                    <>
                      <dt className="text-muted-foreground">Clip</dt>
                      <dd>{(last.result.recording.durationMs / 1000).toFixed(1)} s</dd>
                      <dt className="text-muted-foreground">Peak level</dt>
                      <dd>{last.result.recording.peakRms.toFixed(3)}</dd>
                    </>
                  )}
                </dl>
              )}
              {recordingUrl && <audio controls src={recordingUrl} className="mt-3 w-full" />}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>2. Speak back</CardTitle>
          <CardDescription>The browser reads this aloud in {LANGUAGES[lang].label}.</CardDescription>
        </CardHeader>
        <CardContent>
          <SpeakBack key={lang} lang={lang} />
        </CardContent>
      </Card>
    </div>
  );
}
