import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Bell, FileText, History } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { StatusBadge } from "@/features/doctor-dashboard/StatusBadge";
import { PatientLinks } from "@/features/discharge/PatientLinks";
import { ReportTypeBadge } from "@/features/reports/ReportTypeBadge";
import type { Timeline } from "@/shared/api/client";
import { LANGUAGES, isLang } from "@/shared/languages";
import { cn } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { getDischarge, getEpisodeReports, getReminders, getTimeline } from "./api";

const REFRESH_MS = 10_000;
const when = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
const TONE: Record<string, string> = {
  good: "bg-emerald-500",
  warning: "bg-amber-500",
  danger: "bg-red-600",
  neutral: "bg-muted-foreground/40",
};
const ACTOR: Record<string, string> = { patient: "Patient", carer: "Carer", doctor: "Doctor", system: "CareVoice" };
const REMINDER_STATUS: Record<string, string> = {
  pending: "Upcoming",
  done: "Sent",
  failed: "Failed",
  cancelled: "Cancelled",
};

function TimelineList({ timeline }: { timeline: Timeline }) {
  if (timeline.entries.length === 0) return <p className="text-muted-foreground">Nothing has happened yet.</p>;
  return (
    <ol className="relative flex flex-col gap-4 border-l pl-6" aria-label="Timeline">
      {timeline.entries.map((e) => (
        <li key={e.id} className="relative">
          <span className={cn("absolute top-1.5 -left-[1.95rem] size-3 rounded-full ring-4 ring-background", TONE[e.tone])} aria-hidden />
          <p className="text-sm text-muted-foreground">
            <time dateTime={e.at}>{when.format(new Date(e.at))}</time> · {ACTOR[e.actor] ?? e.actor}
          </p>
          <p className="font-medium">
            {e.report_id ? (
              <Link to={`/doctor/reports/${e.report_id}`} className="underline-offset-4 hover:underline">
                {e.title}
              </Link>
            ) : (
              e.title
            )}
          </p>
          {e.detail && <p className="line-clamp-3 text-sm text-muted-foreground" title={e.detail}>{e.detail}</p>}
        </li>
      ))}
    </ol>
  );
}

/** The doctor's view of one care episode: status, reports, reminders and the full timeline. */
export function PatientRecordPage() {
  const { dischargeId = "" } = useParams();
  const discharge = useQuery({ queryKey: ["discharge", dischargeId], queryFn: () => getDischarge(dischargeId), refetchInterval: REFRESH_MS });
  const reports = useQuery({ queryKey: ["reports", "episode", dischargeId], queryFn: () => getEpisodeReports(dischargeId), refetchInterval: REFRESH_MS });
  const reminders = useQuery({ queryKey: ["reminders", dischargeId], queryFn: () => getReminders(dischargeId), refetchInterval: REFRESH_MS });
  const timeline = useQuery({ queryKey: ["timeline", dischargeId], queryFn: () => getTimeline(dischargeId), refetchInterval: REFRESH_MS });

  if (discharge.isPending) return <p className="text-muted-foreground">Loading patient…</p>;
  if (discharge.isError) return <p className="text-destructive">This patient could not be found.</p>;
  const d = discharge.data;
  const lang = d.patient.preferred_language;

  return (
    <div className="flex flex-col gap-5">
      <Button asChild variant="ghost" size="sm" className="w-fit">
        <Link to="/doctor">
          <ArrowLeft aria-hidden /> Patients
        </Link>
      </Button>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {d.patient.name}
            {d.patient.age != null && <span className="text-muted-foreground">, {d.patient.age}</span>}
          </h1>
          <p className="text-muted-foreground">
            {d.card.template_name}
            {d.card.side && ` (${d.card.side} side)`} · day {d.recovery_day} · {isLang(lang) ? LANGUAGES[lang].label : lang}
          </p>
        </div>
        <StatusBadge status={d.status} />
      </div>

      {d.card.extra_instructions.length > 0 && (
        <p className="text-sm">
          <span className="text-muted-foreground">Your extra instructions: </span>
          {d.card.extra_instructions.join("; ")}
        </p>
      )}

      {d.status !== "draft" && d.status !== "closed" && (
        <details className="rounded-lg border p-3">
          <summary className="cursor-pointer font-medium">Patient and carer links</summary>
          <div className="pt-3">
            <PatientLinks dischargeId={d.id} />
          </div>
        </details>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="size-5" aria-hidden /> Reports
            </CardTitle>
          </CardHeader>
          <CardContent>
            {reports.data?.length ? (
              <ul className="divide-y" aria-label="Reports">
                {reports.data.map((r) => (
                  <li key={r.id}>
                    <Link to={`/doctor/reports/${r.id}`} className="flex items-center justify-between gap-3 py-2 hover:bg-muted">
                      <span className="min-w-0">
                        <span className="block text-sm text-muted-foreground">
                          Day {r.recovery_day ?? "?"} · {when.format(new Date(r.created_at))}
                          {r.reported_by === "carer" && " · by carer"}
                        </span>
                        <span className="block truncate">{r.summary_en}</span>
                      </span>
                      <span className="flex shrink-0 items-center gap-2">
                        {r.status === "new" && <Badge variant="secondary">New</Badge>}
                        <ReportTypeBadge type={r.type} />
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted-foreground">No reports yet.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bell className="size-5" aria-hidden /> Reminders
            </CardTitle>
          </CardHeader>
          <CardContent>
            {reminders.data?.length ? (
              <ul className="flex flex-col gap-2" aria-label="Reminders">
                {reminders.data.map((r) => (
                  <li key={r.id} className="flex items-start justify-between gap-3">
                    <span>
                      <span className="block text-sm text-muted-foreground">
                        Day {r.day}, {r.time}
                      </span>
                      {r.text_en}
                    </span>
                    <Badge variant={r.status === "done" ? "secondary" : "outline"}>{REMINDER_STATUS[r.status] ?? r.status}</Badge>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted-foreground">No reminders scheduled.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="size-5" aria-hidden /> Timeline
          </CardTitle>
          <p className="text-sm text-muted-foreground">Everything sent, played, answered and confirmed, with times. Read-only.</p>
        </CardHeader>
        <CardContent>{timeline.data && <TimelineList timeline={timeline.data} />}</CardContent>
      </Card>
    </div>
  );
}
