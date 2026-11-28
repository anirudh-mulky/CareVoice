import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing, Clock } from "lucide-react";
import { useState } from "react";
import type { TodayReminders as TodayData } from "@/shared/api/client";
import { AudioPlayer } from "@/shared/AudioPlayer";
import { useI18n } from "@/shared/i18n";
import type { Lang } from "@/shared/languages";
import { getTodayReminders, markPlayed } from "./api";

type Reminder = TodayData["reminders"][number];

function SentReminder({ token, lang, reminder }: { token: string; lang: Lang; reminder: Reminder }) {
  const queryClient = useQueryClient();
  // Decided once when it first appears: an unheard reminder plays by itself, once.
  const [autoPlay] = useState(() => !reminder.played);
  return (
    <AudioPlayer
      text={reminder.text}
      lang={lang}
      autoPlay={autoPlay}
      onPlayed={() => {
        if (!reminder.message_id) return;
        void markPlayed(token, reminder.message_id).then(() =>
          queryClient.invalidateQueries({ queryKey: ["patient-reminders", token] }),
        );
      }}
    />
  );
}

/** Today's reminder on the patient home ("Time for your eye drops"), in their language. */
export function TodayReminders({ token, lang }: { token: string; lang: Lang }) {
  const { t } = useI18n(lang);
  const today = useQuery({
    queryKey: ["patient-reminders", token],
    queryFn: () => getTodayReminders(token),
    refetchInterval: 10_000,
  });
  const shown = today.data?.reminders.filter((r) => r.state === "sent" || r.state === "upcoming") ?? [];
  if (shown.length === 0) return null;

  return (
    <section aria-labelledby="today-reminder" className="flex flex-col gap-4 rounded-2xl border-2 border-primary/40 bg-card p-5">
      <h2 id="today-reminder" className="flex items-center gap-2 text-xl font-semibold">
        <BellRing className="size-6 shrink-0 text-primary" aria-hidden /> {t("patient.today")}
      </h2>
      {shown.map((r) => (
        <div key={`${r.time}-${r.message_id ?? "upcoming"}`} className="flex flex-col gap-2">
          <p className="flex items-center gap-1 text-sm text-muted-foreground">
            <Clock className="size-4" aria-hidden /> {t("patient.reminder_upcoming", { time: r.time })}
          </p>
          <p>{r.text}</p>
          {r.state === "sent" && <SentReminder key={r.message_id} token={token} lang={lang} reminder={r} />}
        </div>
      ))}
    </section>
  );
}
