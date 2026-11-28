import { useQueryClient } from "@tanstack/react-query";
import { Check, Languages } from "lucide-react";
import { useState } from "react";
import { useI18n } from "@/shared/i18n";
import { LANG_CODES, LANGUAGES, type Lang } from "@/shared/languages";
import { Button } from "@/shared/ui/button";
import { VoiceInput } from "@/shared/VoiceInput";
import { changeLanguage } from "./api";

/** Wrong language? Tap yours, or say it ("Kannada", "ಕನ್ನಡ", "Hindi"…). */
export function LanguageSwitcher({ token, lang }: { token: string; lang: Lang }) {
  const { t } = useI18n(lang);
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState(false);

  const change = async (body: { language?: string; spoken?: string }) => {
    setError(false);
    try {
      await changeLanguage(token, body);
      setOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["patient", token] });
      void queryClient.invalidateQueries({ queryKey: ["patient-reminders", token] });
    } catch {
      setError(true);
    }
  };

  return (
    <>
      <Button variant="outline" size="lg" aria-expanded={open} onClick={() => setOpen((o) => !o)} className="shrink-0">
        <Languages aria-hidden /> <span className="sr-only sm:not-sr-only">{t("language.switch")}</span>
      </Button>
      {open && (
        <div className="absolute inset-x-0 top-full z-20 flex flex-col gap-4 border-b bg-background p-4 shadow-lg">
          <div role="group" aria-label={t("language.switch")} className="grid grid-cols-2 gap-2">
            {LANG_CODES.map((code) => (
              <Button
                key={code}
                size="lg"
                variant={code === lang ? "default" : "outline"}
                lang={code}
                onClick={() => void change({ language: code })}
              >
                {code === lang && <Check aria-hidden />} {LANGUAGES[code].label}
              </Button>
            ))}
          </div>
          <details>
            <summary className="cursor-pointer text-center text-muted-foreground">{t("language.say")}</summary>
            <div className="pt-3">
              <VoiceInput lang={lang} record={false} onText={(spoken) => void change({ spoken })} />
            </div>
          </details>
          {error && (
            <p role="alert" className="text-amber-900">
              {t("common.error")}
            </p>
          )}
        </div>
      )}
    </>
  );
}
