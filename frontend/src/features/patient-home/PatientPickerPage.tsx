import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import { SimulateDayButton } from "@/features/demo/SimulateDayButton";
import { LANGUAGES, isLang } from "@/shared/languages";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { getDemoLinks } from "./api";

/**
 * Demo entry for "I'm a patient". Real patients open the link their hospital sends them
 * (by WhatsApp or SMS in production); here you can pick a demo patient.
 */
export function PatientPickerPage() {
  const links = useQuery({ queryKey: ["demo-links"], queryFn: getDemoLinks });
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 py-8">
      <div>
        <Badge variant="outline">Demo</Badge>
        <h1 className="mt-2 text-2xl font-semibold">Open a patient's link</h1>
        <p className="text-muted-foreground">
          Patients don't log in. Each one gets a private link from the hospital, the same link a WhatsApp message would
          carry. Pick a demo patient to open theirs.
        </p>
        <div className="mt-3">
          <SimulateDayButton />
        </div>
      </div>
      {links.isPending && <p className="text-muted-foreground">Loading…</p>}
      {links.isError && <p className="text-destructive">Could not load demo patients.</p>}
      {links.data?.length === 0 && (
        <p className="text-muted-foreground">
          No discharges have been sent yet. <Link to="/doctor/discharge/new" className="underline">Discharge a patient</Link> first.
        </p>
      )}
      {links.data?.map((d) => (
        <Card key={d.patient_name}>
          <CardHeader>
            <CardTitle>{d.patient_name}</CardTitle>
            <CardDescription>
              {d.template_name} · {isLang(d.language) ? LANGUAGES[d.language].label : d.language}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {d.links.map((l) => (
              <Button key={l.url} asChild variant={l.recipient_type === "patient" ? "default" : "outline"}>
                <Link to={l.url}>
                  <ExternalLink aria-hidden />
                  {l.recipient_type === "patient" ? "Open as patient" : `Open as carer (${l.name}, ${l.relation})`}
                </Link>
              </Button>
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
