import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleAlert, Loader2, PhoneCall } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { answerTeachback, getTeachback } from "@/features/patient-home/api";
import { usePatient } from "@/features/patient-home/usePatient";
import type { TeachbackResult } from "@/shared/api/client";
import { AudioPlayer } from "@/shared/AudioPlayer";
import { useI18n } from "@/shared/i18n";
import { Button } from "@/shared/ui/button";
import { LOW_CONFIDENCE } from "@/shared/useVoiceCapture";
import { VoiceInput } from "@/shared/VoiceInput";

function FlagList({ title, items, tone }: { title: string; items: { id: string; label: string }[]; tone: "ok" | "missed" }) {
  if (items.length === 0) return null;
  const ok = tone === "ok";
  return (
    <section
      className={ok ? "rounded-2xl border bg-emerald-50 p-5" : "rounded-2xl border-2 border-amber-300 bg-amber-50 p-5"}
    >
      <h2 className={ok ? "mb-3 font-semibold text-emerald-900" : "mb-3 font-semibold text-amber-900"}>{title}</h2>
      <ul className="space-y-2" data-tone={tone}>
        {items.map((f) => (
          <li key={f.id} className="flex gap-3">
            {ok ? (
              <CheckCircle2 className="mt-1 size-5 shrink-0 text-emerald-700" aria-hidden />
            ) : (
              <CircleAlert className="mt-1 size-5 shrink-0 text-amber-700" aria-hidden />
            )}
            <span>{f.label}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * Spoken teach-back: the app asks when to come back to the hospital, the patient answers by
 * voice (or types), missed warning signs are re-explained aloud, and there are two tries.
 */
export function TeachbackPage() {
  const { token, lang } = usePatient();
  const { t } = useI18n(lang);
  const queryClient = useQueryClient();
  const state = useQuery({ queryKey: ["teachback", token], queryFn: () => getTeachback(token) });
  const [result, setResult] = useState<TeachbackResult | null>(null);
  const [said, setSaid] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  if (state.isPending) return <p className="text-muted-foreground">{t("patient.loading")}</p>;
  if (state.isError) return <p role="alert">{t("teachback.error")}</p>;
  const data = state.data;

  const submit = async (text: string) => {
    setBusy(true);
    setError(false);
    setSaid(text);
    try {
      setResult(await answerTeachback(token, text, lang));
      for (const key of [["teachback", token], ["patient", token], ["patient-messages", token]]) {
        void queryClient.invalidateQueries({ queryKey: key });
      }
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  // The latest result: from this visit, or from an earlier visit (state.last).
  const shown = result ?? data.last;
  const done = result ? result.outcome !== "try_again" : data.complete;
  const tryNumber = (result?.try_number ?? data.tries_used) + 1;
  const understood = done && (shown ? shown.outcome === "understood" : data.discharge_status === "understood");

  return (
    <>
      <h1 className="text-2xl font-bold">{t("teachback.title")}</h1>

      {said && (
        <p className="rounded-2xl bg-secondary p-4">
          <span className="block text-sm text-muted-foreground">{t("teachback.you_said")}</span>“{said}”
        </p>
      )}

      {shown && (
        <>
          <FlagList title={t("teachback.named")} items={shown.mentioned} tone="ok" />
          <FlagList title={t("teachback.missed")} items={shown.missed} tone="missed" />
          <div className="rounded-2xl border bg-card p-5">
            <p className="mb-3">{shown.reply}</p>
            <AudioPlayer key={`${shown.try_number}-${shown.outcome}`} text={shown.reply} lang={lang} autoPlay={!!result} />
          </div>
        </>
      )}

      {!done && (
        <section className="flex flex-col items-center gap-4 rounded-2xl border bg-card p-6 text-center">
          <p className="text-sm font-medium text-muted-foreground">
            {t("teachback.try", { n: tryNumber, max: data.max_tries })}
          </p>
          <h2 className="text-xl font-semibold">{shown ? t("teachback.try_again") : data.question}</h2>
          {!shown && <AudioPlayer text={data.question} lang={lang} autoPlay />}
          {busy ? (
            <p className="flex items-center gap-2 py-10">
              <Loader2 className="size-5 animate-spin" aria-hidden /> {t("teachback.checking")}
            </p>
          ) : (
            <VoiceInput key={tryNumber} lang={lang} minConfidence={LOW_CONFIDENCE} onText={(text) => void submit(text)} />
          )}
          {error && (
            <p role="alert" className="rounded-md bg-amber-50 px-4 py-3 text-amber-900">
              {t("teachback.error")}
            </p>
          )}
        </section>
      )}

      {done && (
        <section className="flex flex-col items-center gap-4 rounded-2xl border bg-card p-6 text-center">
          {understood ? (
            <CheckCircle2 className="size-14 text-emerald-600" aria-hidden />
          ) : (
            <PhoneCall className="size-14 text-amber-600" aria-hidden />
          )}
          <p role="status" className="text-xl font-semibold">
            {understood ? t("teachback.understood") : t("teachback.followup")}
          </p>
          <Button asChild size="lg">
            <Link to={`/p/${token}`}>{t("teachback.back")}</Link>
          </Button>
        </section>
      )}
    </>
  );
}
