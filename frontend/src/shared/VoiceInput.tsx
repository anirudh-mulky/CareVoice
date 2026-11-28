import { type ReactNode, useState } from "react";
import { useI18n } from "./i18n";
import type { Lang } from "./languages";
import { MicButton } from "./MicButton";
import { TypeInstead } from "./TypeInstead";
import { type CaptureResult, useVoiceCapture } from "./useVoiceCapture";

type VoiceInputProps = {
  lang: Lang;
  /** Spoken or typed text. `typed` is true when it came from the keyboard. */
  onText: (text: string, details: { typed: boolean; result?: CaptureResult }) => void;
  onNotHeard?: (failures: number) => void;
  record?: boolean;
  /** Ask once to repeat when recognition confidence is below this (see LOW_CONFIDENCE). */
  minConfidence?: number;
  /** Shown after two failed tries in a row, e.g. symptom icons and Call hospital. */
  fallback?: ReactNode;
};

/** After this many failed tries in a row, open "type instead" and show the fallback. */
export const FAILURES_BEFORE_FALLBACK = 2;

/** Big mic + live transcript + retry message + "type instead": the standard voice step. */
export function VoiceInput({ lang, onText, onNotHeard, record, minConfidence, fallback }: VoiceInputProps) {
  const { t } = useI18n(lang);
  const [failures, setFailures] = useState(0);
  const capture = useVoiceCapture({
    lang,
    record,
    minConfidence,
    onNotHeard: (n) => {
      setFailures(n);
      onNotHeard?.(n);
    },
    onResult: (result) => {
      setFailures(0);
      onText(result.text, { typed: false, result });
    },
  });
  const struggling = failures >= FAILURES_BEFORE_FALLBACK;
  const listening = capture.status === "listening";

  return (
    <div className="flex flex-col items-center gap-4 text-center">
      <MicButton
        status={capture.status}
        level={capture.level}
        onPress={capture.toggle}
        label={listening ? t("mic.stop") : t("mic.start")}
        disabled={!capture.supported}
      />
      <p className="text-lg font-medium" aria-live="polite">
        {capture.status === "processing"
          ? t("mic.processing")
          : listening
            ? t("mic.listening")
            : t("mic.start")}
      </p>
      {listening && capture.secondsLeft <= 10 && (
        <p className="text-sm text-muted-foreground">{t("mic.time_left", { seconds: capture.secondsLeft })}</p>
      )}
      {capture.interim && (
        <p lang={lang} className="max-w-md text-muted-foreground italic">
          “{capture.interim}”
        </p>
      )}
      {capture.message && (
        <p role="alert" lang={lang} className="max-w-md rounded-md bg-amber-50 px-4 py-3 text-amber-900">
          {t(capture.message)}
        </p>
      )}
      <TypeInstead
        lang={lang}
        open={!capture.supported || capture.message === "mic.permission_denied" || struggling ? true : undefined}
        onSubmit={(text) => onText(text, { typed: true })}
      />
      {(struggling || !capture.supported) && fallback}
    </div>
  );
}
