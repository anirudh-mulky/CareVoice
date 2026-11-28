import { useQuery } from "@tanstack/react-query";
import {
  MessageCircle,
  Phone,
  RotateCcw,
  ScrollText,
  WifiOff,
} from "lucide-react";
import { NavLink, Outlet, useParams } from "react-router-dom";
import { useI18n } from "@/shared/i18n";
import { cn } from "@/shared/lib/utils";
import { Button } from "@/shared/ui/button";
import { ApiError, getSystemStatus } from "@/shared/api/client";
import { ErrorBoundary } from "@/shared/ErrorBoundary";
import { VoiceServicesProvider } from "@/shared/VoiceServicesProvider";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { type PatientContext, uiLang, usePatientHome } from "./usePatient";

/**
 * Patient and carer shell: big text, the hospital's Call button on every screen, and the
 * emergency disclaimer in the patient's language. Opened from the link the hospital sends.
 */
export function PatientLayout() {
  const { token = "" } = useParams();
  const home = usePatientHome(token);
  const lang = uiLang(home.data?.ui_language ?? home.data?.language);
  const { t } = useI18n(lang);
  const phone = home.data?.hospital.phone;
  const status = useQuery({
    queryKey: ["system-status"],
    queryFn: getSystemStatus,
    staleTime: 60_000,
  });
  // Real speech was asked for but is not available (no key, or down): browser speech instead.
  const basicVoice =
    status.data?.mode === "real" &&
    status.data.providers.some(
      (p) => (p.kind === "stt" || p.kind === "tts") && p.mode === "demo",
    );
  const linkInvalid =
    home.error instanceof ApiError && home.error.code === "link_invalid";

  return (
    <VoiceServicesProvider token={token}>
      <div
        lang={lang}
        className="mx-auto flex min-h-svh w-full max-w-xl flex-col bg-background text-lg"
      >
        <header className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b bg-background/95 px-4 py-3 backdrop-blur">
          <div className="flex min-w-0 items-center gap-2">
            <img src="/favicon.svg" alt="" className="size-8 shrink-0" />
            <span className="hidden truncate font-semibold sm:inline">
              {home.data?.hospital.name ?? "CareVoice"}
            </span>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {home.data && <LanguageSwitcher token={token} lang={lang} />}
            {phone && (
              <Button
                asChild
                size="lg"
                variant="destructive"
                className="shrink-0"
              >
                <a href={`tel:${phone.replace(/\s/g, "")}`}>
                  <Phone aria-hidden /> {t("common.call_hospital")}
                </a>
              </Button>
            )}
          </div>
        </header>

        {basicVoice && (
          <p
            role="status"
            className="bg-amber-100 px-4 py-2 text-center text-sm text-amber-900"
          >
            {t("common.basic_voice")}
          </p>
        )}

        {home.data && (
          <nav
            aria-label={t("patient.home")}
            className="grid grid-cols-2 border-b"
          >
            {[
              {
                to: `/p/${token}`,
                label: t("patient.home"),
                icon: ScrollText,
                end: true,
              },
              {
                to: `/p/${token}/chat`,
                label: t("patient.messages"),
                icon: MessageCircle,
                end: false,
              },
            ].map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center justify-center gap-2 py-3 font-medium",
                    isActive
                      ? "border-b-4 border-primary text-primary"
                      : "text-muted-foreground",
                  )
                }
              >
                <Icon className="size-5" aria-hidden /> {label}
              </NavLink>
            ))}
          </nav>
        )}

        <main className="flex flex-1 flex-col gap-5 px-4 py-5">
          {home.isPending && (
            <p className="text-muted-foreground">{t("patient.loading")}</p>
          )}
          {home.isError && !home.data && (
            <div
              role="alert"
              className="flex flex-col items-start gap-3 rounded-lg bg-amber-50 p-4 text-amber-900"
            >
              {linkInvalid ? (
                <p>{t("patient.link_invalid")}</p>
              ) : (
                <>
                  <p className="flex items-start gap-2">
                    <WifiOff className="mt-1 size-5 shrink-0" aria-hidden />{" "}
                    {t("patient.network_error")}
                  </p>
                  <Button variant="outline" onClick={() => void home.refetch()}>
                    <RotateCcw aria-hidden /> {t("common.retry")}
                  </Button>
                </>
              )}
            </div>
          )}
          {home.data && (
            <ErrorBoundary
              message={t("common.error")}
              retryLabel={t("common.retry")}
            >
              <Outlet
                context={
                  { token, home: home.data, lang } satisfies PatientContext
                }
              />
            </ErrorBoundary>
          )}
        </main>

        <footer className="px-4 pb-6 text-center text-sm text-muted-foreground">
          {t("common.disclaimer")}
        </footer>
      </div>
    </VoiceServicesProvider>
  );
}
