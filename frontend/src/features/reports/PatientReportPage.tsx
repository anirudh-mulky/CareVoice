import { useQueryClient } from "@tanstack/react-query";
import { Check, CheckCircle2, CloudOff, Languages, Loader2, Siren, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { changeLanguage, getMessages } from "@/features/patient-home/api";
import { usePatient } from "@/features/patient-home/usePatient";
import type { ChatMessage, ConfirmOut, ReadBack } from "@/shared/api/client";
import { AudioPlayer } from "@/shared/AudioPlayer";
import { useI18n } from "@/shared/i18n";
import { LANGUAGES, isLang } from "@/shared/languages";
import { enqueue, isOffline, pending, remove } from "@/shared/offlineQueue";
import { Button } from "@/shared/ui/button";
import { type CaptureResult, LOW_CONFIDENCE } from "@/shared/useVoiceCapture";
import { FAILURES_BEFORE_FALLBACK, VoiceInput } from "@/shared/VoiceInput";
import { confirmReport, createIconReport, createReport, uploadAudio } from "./api";
import { SymptomIcons } from "./SymptomIcons";

type Step = "speak" | "confirm" | "sent";

/**
 * Patient (or carer) reports a problem by voice: speak -> hear the read-back in their own
 * language -> yes sends the English report to the doctor, no asks them to say it again.
 */
export function PatientReportPage() {
  const { token, lang, home } = usePatient();
  const { t } = useI18n(lang);
  const queryClient = useQueryClient();
  const [step, setStep] = useState<Step>("speak");
  const [readBack, setReadBack] = useState<ReadBack | null>(null);
  const [notice, setNotice] = useState<ConfirmOut | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [round, setRound] = useState(0);
  const [safety, setSafety] = useState<ChatMessage | null>(null);
  const [rejections, setRejections] = useState(0);
  const [queued, setQueued] = useState(false);
  const [sendingQueued, setSendingQueued] = useState(false);

  const run = async (work: () => Promise<void>) => {
    setBusy(true);
    setError(false);
    try {
      await work();
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  const showReadBack = (out: ReadBack) => {
    setReadBack(out);
    setNotice(null);
    setStep("confirm");
  };

  const onSpoken = (text: string, result?: CaptureResult) =>
    run(async () => {
      try {
        const out = await createReport(token, text, lang, result?.confidence);
        if (result?.recording) void uploadAudio(token, out.report_id, result.recording);
        showReadBack(out);
      } catch (err) {
        if (!isOffline(err)) throw err;
        // No network: keep what they said (and the recording) and send it when back online.
        await enqueue({
          token,
          transcript: text,
          language: lang,
          confidence: result?.confidence ?? null,
          audio: result?.recording?.blob,
          mimeType: result?.recording?.mimeType,
        });
        setQueued(true);
      }
    });

  const onIcons = (icons: string[]) => run(async () => showReadBack(await createIconReport(token, icons, lang)));

  // Send anything saved while offline: on opening this screen and when the network returns.
  const flush = useCallback(async () => {
    const [first] = await pending(token);
    if (!first) return;
    setSendingQueued(true);
    try {
      const out = await createReport(token, first.transcript, first.language, first.confidence);
      if (first.audio) {
        void uploadAudio(token, out.report_id, {
          blob: first.audio,
          mimeType: first.mimeType ?? "audio/webm",
          durationMs: 0,
          peakRms: 0,
          check: { ok: true },
        });
      }
      await remove(first.id);
      setQueued((await pending(token)).length > 0);
      showReadBack(out);
    } catch {
      setQueued(true); // still offline: try again later
    } finally {
      setSendingQueued(false);
    }
  }, [token]);

  useEffect(() => {
    const first = setTimeout(() => void flush(), 0);
    const online = () => void flush();
    globalThis.addEventListener("online", online);
    return () => {
      clearTimeout(first);
      globalThis.removeEventListener("online", online);
    };
  }, [flush]);

  const switchLanguage = (code: string) =>
    run(async () => {
      await changeLanguage(token, { language: code });
      await queryClient.invalidateQueries({ queryKey: ["patient", token] });
    });

  const answer = (body: { answer?: boolean; transcript?: string }) =>
    run(async () => {
      if (!readBack) return;
      const before = new Set((await getMessages(token).catch(() => [])).map((m) => m.id));
      const out = await confirmReport(token, readBack.report_id, body);
      setNotice(out);
      if (out.outcome === "sent") {
        // A red flag sends an automatic safety message: show and say it straight away.
        const after = await getMessages(token).catch(() => []);
        setSafety(after.find((m) => m.kind === "safety" && !before.has(m.id)) ?? null);
        setStep("sent");
        void queryClient.invalidateQueries({ queryKey: ["patient-messages", token] });
        void queryClient.invalidateQueries({ queryKey: ["patient", token] });
      } else if (out.outcome === "say_again") {
        setRejections((n) => n + 1);
        setReadBack(null);
        setRound((n) => n + 1);
        setStep("speak");
      }
    });

  const reset = () => {
    setStep("speak");
    setReadBack(null);
    setNotice(null);
    setSafety(null);
    setRound((n) => n + 1);
  };

  return (
    <>
      <div>
        <h1 className="text-2xl font-bold">{t("report.title")}</h1>
        {home.viewer.type === "carer" && (
          <p className="mt-2 rounded-lg bg-secondary px-3 py-2 text-base">
            {t("report.carer_note", { patient: home.patient_name })}
          </p>
        )}
      </div>

      {notice && notice.outcome !== "sent" && (
        <div role="status" className="flex flex-col gap-2 rounded-2xl bg-amber-50 p-4 text-amber-900">
          <p>{notice.message}</p>
          <AudioPlayer key={`${notice.report_id}-${notice.outcome}`} text={notice.message} lang={lang} autoPlay />
        </div>
      )}

      {queued && (
        <p role="status" className="flex items-start gap-2 rounded-2xl bg-sky-50 p-4 text-sky-900">
          <CloudOff className="mt-1 size-5 shrink-0" aria-hidden />
          {sendingQueued ? t("offline.sending") : t("offline.queued")}
        </p>
      )}

      {busy && (
        <p className="flex items-center justify-center gap-2 py-10">
          <Loader2 className="size-5 animate-spin" aria-hidden /> {t("report.checking")}
        </p>
      )}

      {!busy && step === "speak" && (
        <section className="flex flex-col items-center gap-4 rounded-2xl border bg-card p-6 text-center">
          <p className="text-muted-foreground">{t("report.hint")}</p>
          <VoiceInput
            key={round}
            lang={lang}
            record
            minConfidence={LOW_CONFIDENCE}
            onText={(text, d) => void onSpoken(text, d.result)}
            fallback={
              rejections < FAILURES_BEFORE_FALLBACK && (
                <SymptomIcons lang={lang} phone={home.hospital.phone} onSend={(icons) => void onIcons(icons)} />
              )
            }
          />
          {/* Said "no" to the read-back twice: offer the icons straight away. */}
          {rejections >= FAILURES_BEFORE_FALLBACK && (
            <SymptomIcons lang={lang} phone={home.hospital.phone} onSend={(icons) => void onIcons(icons)} />
          )}
        </section>
      )}

      {!busy && step === "confirm" && readBack && (
        <section className="flex flex-col gap-5 rounded-2xl border-2 border-primary/40 bg-card p-6">
          <h2 className="text-xl font-semibold">{t("report.is_this_right")}</h2>
          <p className="text-xl" lang={readBack.language}>
            {readBack.read_back}
          </p>
          <AudioPlayer
            key={readBack.report_id}
            text={readBack.read_back}
            lang={isLang(readBack.language) ? readBack.language : lang}
            autoPlay
          />
          {readBack.suggested_language && isLang(readBack.suggested_language) && readBack.suggested_language !== lang && (
            <div className="flex flex-col items-start gap-2 rounded-lg bg-secondary p-3">
              <p>{t("language.spoke_other", { language: LANGUAGES[readBack.suggested_language].label })}</p>
              <Button variant="outline" onClick={() => readBack.suggested_language && void switchLanguage(readBack.suggested_language)}>
                <Languages aria-hidden /> {t("language.use", { language: LANGUAGES[readBack.suggested_language].label })}
              </Button>
            </div>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <Button size="lg" className="h-auto min-h-16 text-lg whitespace-normal" onClick={() => answer({ answer: true })}>
              <Check aria-hidden /> {t("report.yes")}
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="h-auto min-h-16 text-lg whitespace-normal"
              onClick={() => answer({ answer: false })}
            >
              <X aria-hidden /> {t("report.no")}
            </Button>
          </div>
          <details className="text-center">
            <summary className="cursor-pointer text-muted-foreground">{t("report.say_yes_no")}</summary>
            <div className="pt-4">
              <VoiceInput key={`yn-${readBack.report_id}`} lang={lang} record={false} onText={(text) => answer({ transcript: text })} />
            </div>
          </details>
        </section>
      )}

      {!busy && step === "sent" && safety && (
        <section role="alert" className="flex flex-col gap-3 rounded-2xl bg-red-600 p-5 text-white">
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <Siren className="size-6 shrink-0" aria-hidden /> {t("patient.alert_title")}
          </h2>
          <p>{safety.text}</p>
          <AudioPlayer text={safety.text} lang={lang} autoPlay />
        </section>
      )}

      {!busy && step === "sent" && notice && (
        <section className="flex flex-col items-center gap-4 rounded-2xl border bg-card p-6 text-center">
          <CheckCircle2 className="size-14 text-emerald-600" aria-hidden />
          <h2 className="text-xl font-semibold">{t("report.sent_title")}</h2>
          <p role="status">{notice.message}</p>
          <AudioPlayer text={notice.message} lang={lang} autoPlay={!safety} />
          <div className="flex flex-wrap justify-center gap-2">
            <Button size="lg" variant="outline" onClick={reset}>
              {t("report.another")}
            </Button>
            <Button asChild size="lg">
              <Link to={`/p/${token}`}>{t("report.back")}</Link>
            </Button>
          </div>
        </section>
      )}

      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-4 py-3 text-red-900">
          {t("report.error")}
        </p>
      )}
    </>
  );
}
