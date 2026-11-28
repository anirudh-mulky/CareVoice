import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, Pill, UserRound } from "lucide-react";
import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { StatusBadge } from "@/features/doctor-dashboard/StatusBadge";
import { ReportActionsPanel } from "@/features/outcomes/ReportActionsPanel";
import type { ReportDetail } from "@/shared/api/client";
import { LANGUAGES, isLang } from "@/shared/languages";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { getReport, markSeen } from "./api";
import { ReportTypeBadge } from "./ReportTypeBadge";

const REASONS: Record<string, string> = {
  red_flag: "Matches a red flag in your template",
  low_confidence: "The app was not sure what this means, so it is treated as urgent",
  low_stt_confidence: "The speech was hard to hear, so it is treated as urgent",
  minor_match: "Matches a minor symptom in your template",
  no_match: "Matches nothing in your template: please reply",
};

const languageLabel = (code: string) => (isLang(code) ? LANGUAGES[code].label : code);

function Facts({ report }: { report: ReportDetail }) {
  const time = new Date(report.created_at).toLocaleString();
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
      <div>
        <dt className="text-muted-foreground">Recovery day</dt>
        <dd className="text-lg font-semibold">Day {report.recovery_day ?? "?"}</dd>
      </div>
      <div>
        <dt className="text-muted-foreground">Template</dt>
        <dd className="font-medium">{report.template_name}</dd>
      </div>
      <div>
        <dt className="text-muted-foreground">Language</dt>
        <dd className="font-medium">{languageLabel(report.language)}</dd>
      </div>
      <div>
        <dt className="text-muted-foreground">Received</dt>
        <dd className="font-medium">{time}</dd>
      </div>
    </dl>
  );
}

/** The doctor's English report beside the patient's own words, with audio and medicines. */
export function DoctorReportPage() {
  const { reportId = "" } = useParams();
  const queryClient = useQueryClient();
  const report = useQuery({ queryKey: ["report", reportId], queryFn: () => getReport(reportId) });
  const isNew = report.data?.status === "new";

  // Opening a report marks it seen.
  useEffect(() => {
    if (!isNew) return;
    void markSeen(reportId).then((seen) => {
      queryClient.setQueryData(["report", reportId], seen);
      void queryClient.invalidateQueries({ queryKey: ["reports"] });
      void queryClient.invalidateQueries({ queryKey: ["discharges"] });
    });
  }, [isNew, reportId, queryClient]);

  if (report.isPending) return <p className="text-muted-foreground">Loading report…</p>;
  if (report.isError) return <p className="text-destructive">This report could not be found.</p>;
  const r = report.data;
  const alert = r.type === "alert";

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
            {r.patient_name}
            {r.patient_age != null && <span className="text-muted-foreground">, {r.patient_age}</span>}
          </h1>
          <p className="text-muted-foreground">
            Symptom report ·{" "}
            <Link to={`/doctor/patients/${r.discharge_id}`} className="underline underline-offset-4">
              Patient record and timeline
            </Link>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ReportTypeBadge type={r.type} />
          {r.reported_by === "carer" && (
            <Badge variant="secondary">
              <UserRound aria-hidden /> Reported by carer
            </Badge>
          )}
          {r.needs_review && <Badge variant="destructive">Needs review</Badge>}
          <span className="flex items-center gap-1 text-sm text-muted-foreground">
            Patient status: <StatusBadge status={r.discharge_status} />
          </span>
        </div>
      </div>

      {alert && (
        <div role="alert" className="flex gap-3 rounded-lg border-2 border-red-300 bg-red-50 p-4 text-red-900">
          <AlertTriangle className="mt-0.5 size-5 shrink-0" aria-hidden />
          <div>
            <p className="font-semibold">Possible red flag: contact this patient today.</p>
            {r.red_flags.length > 0 && (
              <ul className="mt-1 list-disc pl-5">
                {r.red_flags.map((f) => (
                  <li key={f.id}>{f.label_en}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      <Card>
        <CardContent className="pt-6">
          <Facts report={r} />
        </CardContent>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>In English</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <p className="text-lg">{r.summary_en}</p>
            {r.translation_en ? (
              <p>
                <span className="block text-sm text-muted-foreground">Translation of what they said</span>“
                {r.translation_en}”
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">
                No full translation available (demo translator). The summary above lists what was recognised.
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Patient's own words ({languageLabel(r.language)})</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <p className="text-lg" lang={r.language}>
              “{r.transcript_native}”
            </p>
            {r.audio_url ? (
              <audio controls src={r.audio_url} className="w-full" aria-label="Original recording" />
            ) : (
              <p className="text-sm text-muted-foreground">No recording (typed, or the browser could not record).</p>
            )}
            {r.read_back_native && (
              <p className="text-sm">
                <span className="block text-muted-foreground">Read back to the patient, who said yes</span>
                <span lang={r.language}>{r.read_back_native}</span>
              </p>
            )}
            {r.stt_confidence != null && (
              <p className="text-sm text-muted-foreground">
                Speech recognition confidence: {Math.round(r.stt_confidence * 100)}%
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <h2 className="text-xl font-semibold">What to do</h2>
      <ReportActionsPanel reportId={r.id} />

      <Card>
        <CardHeader>
          <CardTitle>Symptoms</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {r.symptoms.length === 0 ? (
            <p className="text-muted-foreground">No listed symptom was recognised.</p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="text-muted-foreground">
                <tr>
                  <th className="py-1 pr-3 font-medium">Symptom</th>
                  <th className="py-1 pr-3 font-medium">Where</th>
                  <th className="py-1 pr-3 font-medium">Patient's words for severity</th>
                  <th className="py-1 font-medium">Onset / duration</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {r.symptoms.map((s) => (
                  <tr key={s.name_en}>
                    <td className="py-2 pr-3 font-medium capitalize">{s.name_en}</td>
                    <td className="py-2 pr-3">{s.body_part ?? "—"}</td>
                    <td className="py-2 pr-3">{s.severity_words ?? "—"}</td>
                    <td className="py-2">{[s.onset, s.duration].filter(Boolean).join(", ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <ul className="flex flex-col gap-1 text-sm">
            {r.reasons.map((reason) => (
              <li key={reason} className="text-muted-foreground">
                Why “{r.type}”: {REASONS[reason] ?? reason}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Pill className="size-5" aria-hidden /> Medicines on the care card
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="flex flex-col gap-2">
            {r.medicines.map((m) => (
              <li key={m.name}>
                <span className="font-medium">{m.name}</span>
                <span className="text-muted-foreground"> — {m.instructions}</span>
              </li>
            ))}
          </ul>
          {r.extra_instructions.length > 0 && (
            <p className="mt-3 text-sm">
              <span className="text-muted-foreground">Your extra instructions: </span>
              {r.extra_instructions.join("; ")}
            </p>
          )}
        </CardContent>
      </Card>

    </div>
  );
}
