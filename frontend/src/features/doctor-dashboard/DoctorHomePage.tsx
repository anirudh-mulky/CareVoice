import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { FilePlus2, Inbox, Link2, Search, UserRound } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { SimulateDayButton } from "@/features/demo/SimulateDayButton";
import { PatientLinks } from "@/features/discharge/PatientLinks";
import { listReports } from "@/features/reports/api";
import { ReportTypeBadge } from "@/features/reports/ReportTypeBadge";
import { LANGUAGES, isLang } from "@/shared/languages";
import { cn } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { type DischargeFilter, listDischarges } from "./api";
import { StatusBadge } from "./StatusBadge";

const FILTERS: { value: DischargeFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "alert", label: "Alert" },
  { value: "needs_followup", label: "Needs follow-up" },
  { value: "sent", label: "Sent" },
  { value: "understood", label: "Understood" },
  { value: "draft", label: "Draft" },
];
const REFRESH_MS = 10_000;

function NewReports() {
  const reports = useQuery({ queryKey: ["reports", "new"], queryFn: () => listReports("new"), refetchInterval: REFRESH_MS });
  if (!reports.data?.length) return null;
  return (
    <Card className="border-2 border-red-200">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Inbox className="size-5" aria-hidden /> New reports
          <Badge variant="secondary">{reports.data.length}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="divide-y" aria-label="New reports">
          {reports.data.map((r) => (
            <li key={r.id}>
              <Link
                to={`/doctor/reports/${r.id}`}
                className={cn(
                  "flex flex-wrap items-center justify-between gap-3 rounded-md px-2 py-3 hover:bg-muted",
                  r.type === "alert" && "bg-red-50 hover:bg-red-100",
                )}
              >
                <div className="min-w-0">
                  <p className="font-medium">
                    {r.patient_name}
                    <span className="text-muted-foreground"> · day {r.recovery_day ?? "?"}</span>
                  </p>
                  <p className="truncate text-sm text-muted-foreground">{r.summary_en}</p>
                </div>
                <div className="flex items-center gap-2">
                  {r.reported_by === "carer" && (
                    <Badge variant="outline">
                      <UserRound aria-hidden /> Carer
                    </Badge>
                  )}
                  <ReportTypeBadge type={r.type} />
                </div>
              </Link>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

/** Doctor dashboard: new reports (alerts first), then every patient, searchable and filterable. */
export function DoctorHomePage() {
  const [filter, setFilter] = useState<DischargeFilter>("all");
  const [search, setSearch] = useState("");
  const discharges = useQuery({
    queryKey: ["discharges", filter, search.trim()],
    queryFn: () => listDischarges(filter, search),
    refetchInterval: REFRESH_MS,
    placeholderData: keepPreviousData,
  });
  const [openLinks, setOpenLinks] = useState<string | null>(null);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Patients</h1>
          <p className="text-muted-foreground">Alerts first. Discharge a new patient by speaking one sentence.</p>
        </div>
        <div className="flex flex-wrap items-start gap-3">
          <SimulateDayButton />
          <Button asChild size="lg">
            <Link to="/doctor/discharge/new">
              <FilePlus2 /> New discharge
            </Link>
          </Button>
        </div>
      </div>

      <NewReports />

      <Card>
        <CardHeader className="flex flex-col gap-3">
          <CardTitle>All patients</CardTitle>
          <div className="relative">
            <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name"
              aria-label="Search patients by name"
              className="h-10 w-full rounded-md border bg-background pr-3 pl-9 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
            />
          </div>
          <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-2">
            {FILTERS.map((f) => (
              <Button
                key={f.value}
                size="sm"
                variant={filter === f.value ? "default" : "outline"}
                aria-pressed={filter === f.value}
                onClick={() => setFilter(f.value)}
              >
                {f.label}
              </Button>
            ))}
          </div>
        </CardHeader>
        <CardContent>
          {discharges.isPending && <p className="text-muted-foreground">Loading…</p>}
          {discharges.isError && <p className="text-destructive">Could not load patients.</p>}
          {discharges.data?.length === 0 && <p className="text-muted-foreground">No patients match.</p>}
          <ul className="divide-y" aria-label="Patients">
            {discharges.data?.map((d) => (
              <li key={d.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div>
                  <p className="font-medium">
                    {d.status === "draft" ? (
                      d.patient_name
                    ) : (
                      <Link to={`/doctor/patients/${d.id}`} className="underline-offset-4 hover:underline">
                        {d.patient_name}
                      </Link>
                    )}
                    {d.age != null && <span className="text-muted-foreground">, {d.age}</span>}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {d.template_name} · day {d.recovery_day} ·{" "}
                    {isLang(d.language) ? LANGUAGES[d.language].label : d.language}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {d.status === "draft" && <Badge variant="outline">Not sent</Badge>}
                  <StatusBadge status={d.status} />
                  {d.latest_report_id && (
                    <Button asChild variant="outline" size="sm">
                      <Link to={`/doctor/reports/${d.latest_report_id}`}>
                        {d.new_reports > 0 ? `${d.new_reports} new report${d.new_reports > 1 ? "s" : ""}` : "Last report"}
                      </Link>
                    </Button>
                  )}
                  {d.status !== "draft" && (
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-expanded={openLinks === d.id}
                      onClick={() => setOpenLinks(openLinks === d.id ? null : d.id)}
                    >
                      <Link2 aria-hidden /> Links
                    </Button>
                  )}
                </div>
                {openLinks === d.id && (
                  <div className="w-full">
                    <PatientLinks dischargeId={d.id} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
