import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { LANGUAGES, isLang } from "@/shared/languages";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { getTemplate } from "./api";

function Section({ title, children, tone }: { title: string; children: ReactNode; tone?: "danger" }) {
  return (
    <Card className={tone === "danger" ? "border-red-200 bg-red-50/40" : undefined}>
      <CardHeader>
        <CardTitle className={tone === "danger" ? "flex items-center gap-2 text-red-800" : undefined}>
          {tone === "danger" && <AlertTriangle className="size-5" aria-hidden />}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function Bullets({ items }: { items: string[] }) {
  if (!items.length) return <p className="text-muted-foreground">None</p>;
  return (
    <ul className="list-disc space-y-1 pl-5">
      {items.map((i) => (
        <li key={i}>{i}</li>
      ))}
    </ul>
  );
}

export function TemplateDetailPage() {
  const { templateId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const version = params.get("version") ? Number(params.get("version")) : undefined;
  const tpl = useQuery({ queryKey: ["template", templateId, version], queryFn: () => getTemplate(templateId, version) });

  if (tpl.isPending) return <p className="text-muted-foreground">Loading…</p>;
  if (tpl.isError) return <p className="text-destructive">Template not found.</p>;
  const t = tpl.data;
  const medicines = t.medicines ?? [];
  const minors = t.minor_symptoms ?? [];
  const reminders = t.reminders ?? [];

  return (
    <div className="flex flex-col gap-5">
      <Button asChild variant="ghost" size="sm" className="w-fit">
        <Link to="/doctor/templates">
          <ArrowLeft /> All templates
        </Link>
      </Button>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t.name}</h1>
          <p className="text-muted-foreground">
            {t.condition} · follow-up on day {t.follow_up_day ?? "—"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {t.languages.map((l) => (
            <Badge key={l} variant="secondary">
              {isLang(l) ? LANGUAGES[l].label : l}
            </Badge>
          ))}
          {t.versions.length > 1 && (
            <select
              aria-label="Version"
              value={t.version}
              onChange={(e) => setParams({ version: e.target.value })}
              className="h-8 rounded-md border bg-background px-2 text-sm"
            >
              {t.versions.map((v) => (
                <option key={v} value={v}>
                  Version {v}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      <Section title="Red flags: come to hospital today" tone="danger">
        <Bullets items={t.red_flags.map((f) => f.label_en)} />
      </Section>

      <Section title="Medicines">
        {medicines.length ? (
          <table className="w-full text-left text-sm">
            <thead className="text-muted-foreground">
              <tr>
                <th className="py-1 font-medium">Medicine</th>
                <th className="py-1 font-medium">Dose</th>
                <th className="py-1 font-medium">How often</th>
                <th className="py-1 font-medium">Days</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {medicines.map((m) => (
                <tr key={m.name}>
                  <td className="py-2 pr-3 font-medium">{m.name}</td>
                  <td className="py-2 pr-3">{m.dose ?? "—"}</td>
                  <td className="py-2 pr-3">{m.frequency ?? "—"}</td>
                  <td className="py-2">{m.duration_days ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-muted-foreground">None</p>
        )}
      </Section>

      <div className="grid gap-5 sm:grid-cols-2">
        <Section title="Do">
          <Bullets items={t.dos ?? []} />
        </Section>
        <Section title="Don't">
          <Bullets items={t.donts ?? []} />
        </Section>
      </div>

      <Section title="Minor symptoms and your remedies">
        <dl className="space-y-3">
          {minors.map((m) => (
            <div key={m.id}>
              <dt className="font-medium">{m.symptom_en}</dt>
              <dd className="text-muted-foreground">{m.remedy_en}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section title="Reminders">
        <ul className="space-y-1">
          {reminders.map((r) => (
            <li key={`${r.day}-${r.time}`}>
              <span className="font-medium">
                Day {r.day}, {r.time}:
              </span>{" "}
              {r.message_en}
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
