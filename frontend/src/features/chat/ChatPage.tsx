import { useQuery } from "@tanstack/react-query";
import { getMessages, markPlayed } from "@/features/patient-home/api";
import { usePatient } from "@/features/patient-home/usePatient";
import { AudioPlayer } from "@/shared/AudioPlayer";
import { useI18n } from "@/shared/i18n";
import { isLang } from "@/shared/languages";
import { cn } from "@/shared/lib/utils";

/** WhatsApp-style chat: care-team voice notes on the left, the patient's own words on the right. */
export function ChatPage() {
  const { token, lang } = usePatient();
  const { t } = useI18n(lang);
  const messages = useQuery({
    queryKey: ["patient-messages", token],
    queryFn: () => getMessages(token),
    refetchInterval: 10_000,
  });
  const time = new Intl.DateTimeFormat(`${lang}-IN`, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

  if (messages.isPending) return <p className="text-muted-foreground">{t("patient.loading")}</p>;
  if (!messages.data?.length) return <p className="text-muted-foreground">{t("chat.empty")}</p>;

  return (
    <ol className="flex flex-col gap-4 rounded-2xl bg-[#efeae2] p-3" aria-label={t("patient.messages")}>
      {messages.data.map((m) => {
        const mine = m.direction === "to_doctor";
        const msgLang = isLang(m.language) ? m.language : lang;
        return (
          <li key={m.id} className={cn("flex", mine ? "justify-end" : "justify-start")}>
            <div
              className={cn(
                "flex max-w-[85%] flex-col gap-3 rounded-2xl px-4 py-3 shadow-sm",
                mine ? "rounded-br-sm bg-[#d9fdd3]" : "rounded-bl-sm bg-white",
                m.kind === "safety" && "border-2 border-red-400",
              )}
            >
              <p className="text-sm font-semibold text-primary">{mine ? t("chat.you") : t("chat.care_team")}</p>
              {!mine && (
                <AudioPlayer
                  text={m.text}
                  lang={msgLang}
                  src={m.audio_url}
                  onPlayed={() => void markPlayed(token, m.id)}
                />
              )}
              <p lang={msgLang} className="whitespace-pre-line">
                {m.text}
              </p>
              <p className="self-end text-xs text-muted-foreground">{time.format(new Date(m.created_at))}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
