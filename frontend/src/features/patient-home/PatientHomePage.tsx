import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CalendarCheck, CheckCircle2, Mail, Mic, MessageCircleQuestion, Siren } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { AudioPlayer } from "@/shared/AudioPlayer";
import { useI18n } from "@/shared/i18n";
import { Button } from "@/shared/ui/button";
import { getMessages, markPlayed } from "./api";
import { TodayReminders } from "./TodayReminders";
import { uiLang, usePatient } from "./usePatient";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border bg-card p-5">
      <h2 className="mb-3 text-xl font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function List({ items }: { items: string[] }) {
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item} className="flex gap-3">
          <span className="mt-2.5 size-2 shrink-0 rounded-full bg-primary" aria-hidden />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

/** Patient home: red flags first, everything readable and listenable, the big mic below. */
export function PatientHomePage() {
  const { token, home, lang } = usePatient();
  const { t } = useI18n(lang);
  const card = home.card;
  // Card content is spoken in the card's own language (English when not yet translated).
  const cardLang = uiLang(card.language);
  const messages = useQuery({ queryKey: ["patient-messages", token], queryFn: () => getMessages(token) });
  const careNote = messages.data?.filter((m) => m.kind === "instructions").at(-1);
  const safety = home.status === "alert" ? messages.data?.filter((m) => m.kind === "safety").at(-1) : undefined;
  const lastFromTeam = messages.data?.filter((m) => m.direction === "to_patient").at(-1);
  const doctorNote =
    lastFromTeam && (lastFromTeam.kind === "remedy" || lastFromTeam.kind === "doctor_reply") && !lastFromTeam.played_at
      ? lastFromTeam
      : undefined;
  const redFlagsSpeech = [card.red_flags_title, ...card.red_flags].join(". ");

  return (
    <>
      <div>
        <h1 className="text-2xl font-bold">{home.patient_name}</h1>
        <p className="text-muted-foreground">{t("patient.day", { day: home.recovery_day })}</p>
        {home.viewer.type === "carer" && (
          <p className="mt-2 rounded-lg bg-secondary px-3 py-2 text-base">
            {t("patient.carer_view", { patient: home.patient_name })}
          </p>
        )}
        {!card.translated && (
          <p role="note" className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-base text-amber-900">
            {t("patient.not_translated")}
          </p>
        )}
      </div>

      {home.status === "alert" && (
        <section role="alert" className="flex flex-col gap-3 rounded-2xl bg-red-600 p-5 text-white">
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <Siren className="size-6 shrink-0" aria-hidden /> {t("patient.alert_title")}
          </h2>
          {safety && (
            <>
              <p>{safety.text}</p>
              <AudioPlayer text={safety.text} lang={lang} onPlayed={() => void markPlayed(token, safety.id)} />
            </>
          )}
        </section>
      )}
      {doctorNote && (
        <Link
          to={`/p/${token}/chat`}
          className="flex items-center gap-3 rounded-2xl border-2 border-primary bg-primary/5 p-4 font-semibold"
        >
          <Mail className="size-6 shrink-0 text-primary" aria-hidden />
          <span className="flex-1">{t("patient.new_message")}</span>
          <span className="text-primary">{t("patient.open_messages")}</span>
        </Link>
      )}

      <section aria-labelledby="red-flags" className="rounded-2xl border-2 border-red-300 bg-red-50 p-5">
        <h2 id="red-flags" className="mb-3 flex items-start gap-2 text-xl font-bold text-red-800">
          <AlertTriangle className="mt-0.5 size-6 shrink-0" aria-hidden />
          {card.red_flags_title}
        </h2>
        <ul className="mb-4 space-y-2 text-red-950">
          {card.red_flags.map((flag) => (
            <li key={flag} className="flex gap-3">
              <span className="mt-2.5 size-2 shrink-0 rounded-full bg-red-600" aria-hidden />
              {flag}
            </li>
          ))}
        </ul>
        <AudioPlayer text={redFlagsSpeech} lang={cardLang} />
        <span className="sr-only">{t("patient.listen_red_flags")}</span>
      </section>

      <TodayReminders token={token} lang={lang} />

      {home.status === "sent" && (
        <section className="flex flex-col gap-3 rounded-2xl border-2 border-primary/40 bg-card p-5">
          <h2 className="flex items-center gap-2 text-xl font-semibold">
            <MessageCircleQuestion className="size-6 shrink-0 text-primary" aria-hidden />
            {t("teachback.title")}
          </h2>
          <p className="text-muted-foreground">{t("teachback.home_hint")}</p>
          <Button asChild size="lg" className="w-fit">
            <Link to={`/p/${token}/teachback`}>{t("teachback.start")}</Link>
          </Button>
        </section>
      )}
      {home.status === "understood" && (
        <p className="flex items-center gap-2 rounded-2xl bg-emerald-50 px-5 py-3 text-emerald-900">
          <CheckCircle2 className="size-5 shrink-0" aria-hidden /> {t("teachback.understood")}
        </p>
      )}

      {careNote && (
        <div className="flex flex-col gap-2 rounded-2xl bg-secondary p-5">
          <p className="font-semibold">{t("patient.listen_all")}</p>
          <AudioPlayer
            text={careNote.text}
            lang={uiLang(careNote.language)}
            src={careNote.audio_url}
            onPlayed={() => void markPlayed(token, careNote.id)}
          />
        </div>
      )}

      {card.medicines.length > 0 && (
        <Section title={card.labels.medicines}>
          <ul className="space-y-3">
            {card.medicines.map((m) => (
              <li key={m.name}>
                <p className="font-semibold" lang="en">
                  {m.name}
                </p>
                <p className="text-muted-foreground">{m.instructions}</p>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {card.dos.length > 0 && (
        <Section title={card.labels.do}>
          <List items={card.dos} />
        </Section>
      )}
      {card.donts.length > 0 && (
        <Section title={card.labels.dont}>
          <List items={card.donts} />
        </Section>
      )}
      {card.extras.length > 0 && (
        <Section title={card.labels.extras}>
          <ul className="space-y-2">
            {card.extras.map((e) => (
              <li key={e.text}>
                <span lang={e.translated ? lang : "en"}>{e.text}</span>
                {!e.translated && (
                  <span className="block text-sm text-muted-foreground">{t("patient.extra_not_translated")}</span>
                )}
              </li>
            ))}
          </ul>
        </Section>
      )}
      {card.follow_up && (
        <div className="flex items-center gap-3 rounded-2xl border bg-card p-5">
          <CalendarCheck className="size-7 shrink-0 text-primary" aria-hidden />
          <p>
            <span className="block text-sm text-muted-foreground">{t("patient.follow_up")}</span>
            {card.follow_up}
          </p>
        </div>
      )}

      <section className="flex flex-col items-center gap-3 rounded-2xl border bg-card p-6 text-center">
        <h2 className="text-xl font-semibold">{t("patient.speak_title")}</h2>
        <p className="text-muted-foreground">{t("patient.speak_hint")}</p>
        <Link
          to={`/p/${token}/report`}
          aria-label={t("mic.start")}
          className="flex size-28 items-center justify-center rounded-full bg-primary text-white shadow-lg transition-transform active:scale-95"
        >
          <Mic className="size-12" aria-hidden />
        </Link>
      </section>
    </>
  );
}
