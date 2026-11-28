import { Droplet, Eye, Phone, Siren, Thermometer, Bandage, Waves, Zap } from "lucide-react";
import { useState } from "react";
import { type MessageKey, useI18n } from "@/shared/i18n";
import type { Lang } from "@/shared/languages";
import { cn } from "@/shared/lib/utils";
import { Button } from "@/shared/ui/button";

/** Same ids as the backend's SYMPTOM_ICONS (lexicon concepts). */
const ICONS = [
  { id: "pain", icon: Zap },
  { id: "redness", icon: Siren },
  { id: "bleeding", icon: Droplet },
  { id: "fever", icon: Thermometer },
  { id: "swelling", icon: Waves },
  { id: "vision_loss", icon: Eye },
  { id: "wound_problem", icon: Bandage },
] as const;

type Props = { lang: Lang; phone?: string | null; onSend: (icons: string[]) => void };

/** Big buttons for when speaking does not work (two failed tries, or two "no"s). */
export function SymptomIcons({ lang, phone, onSend }: Props) {
  const { t } = useI18n(lang);
  const [chosen, setChosen] = useState<string[]>([]);
  const toggle = (id: string) => setChosen((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));

  return (
    <section aria-labelledby="symptom-icons" className="flex w-full flex-col gap-3 text-left">
      <h2 id="symptom-icons" className="text-lg font-semibold">
        {t("icons.title")}
      </h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {ICONS.map(({ id, icon: Icon }) => {
          const on = chosen.includes(id);
          return (
            <button
              key={id}
              type="button"
              aria-pressed={on}
              onClick={() => toggle(id)}
              className={cn(
                "flex min-h-24 flex-col items-center justify-center gap-2 rounded-2xl border-2 p-3 text-center font-medium",
                on ? "border-primary bg-primary/10" : "border-border bg-card",
              )}
            >
              <Icon className="size-8" aria-hidden />
              {t(`icons.${id}` as MessageKey)}
            </button>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-3">
        <Button size="lg" disabled={chosen.length === 0} onClick={() => onSend(chosen)}>
          {t("icons.send")}
        </Button>
        {phone && (
          <Button asChild size="lg" variant="destructive">
            <a href={`tel:${phone.replace(/\s/g, "")}`}>
              <Phone aria-hidden /> {t("common.call_hospital")}
            </a>
          </Button>
        )}
      </div>
    </section>
  );
}
