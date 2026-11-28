import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import { LANGUAGES, isLang } from "@/shared/languages";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { listTemplates } from "./api";

export function TemplatesPage() {
  const templates = useQuery({ queryKey: ["templates"], queryFn: listTemplates });
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Templates</h1>
        <p className="text-muted-foreground">
          Your standard instructions. A discharge uses one, so you only add what is different for each patient.
        </p>
      </div>
      {templates.isPending && <p className="text-muted-foreground">Loading…</p>}
      {templates.isError && <p className="text-destructive">Could not load templates.</p>}
      <div className="grid gap-4 sm:grid-cols-2">
        {templates.data?.map((t) => (
          <Link key={t.id} to={`/doctor/templates/${t.id}`} className="group rounded-xl outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50">
            <Card className="h-full transition-shadow group-hover:shadow-md">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  {t.name}
                  <ChevronRight className="size-5 text-muted-foreground" aria-hidden />
                </CardTitle>
                <CardDescription>Version {t.version}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <p className="text-sm text-muted-foreground">
                  {t.red_flags} red flags · {t.minor_symptoms} minor symptoms · {t.medicines} medicines
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {t.languages.map((l) => (
                    <Badge key={l} variant="secondary">
                      {isLang(l) ? LANGUAGES[l].label : l}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
