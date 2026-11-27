import { ArrowRight, Mic, Smartphone, Stethoscope } from "lucide-react";
import type { ComponentType } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";

type Role = {
  to: string;
  title: string;
  description: string;
  points: string[];
  icon: ComponentType<{ className?: string }>;
};

const ROLES: Role[] = [
  {
    to: "/doctor",
    title: "I'm a doctor",
    description: "Discharge a patient by speaking once.",
    points: ["Dictate the care plan", "Approve before anything is sent", "Read reports in English"],
    icon: Stethoscope,
  },
  {
    to: "/patient",
    title: "I'm a patient",
    description: "Hear your care instructions in your language.",
    points: ["Listen as often as you need", "Tell us how you feel by talking", "Hear your doctor's reply"],
    icon: Smartphone,
  },
];

export function RolePickerPage() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-10 py-10">
      <div className="max-w-xl text-center">
        <div className="mx-auto mb-5 flex size-14 items-center justify-center rounded-full bg-secondary text-primary">
          <Mic className="size-7" aria-hidden />
        </div>
        <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
          The doctor speaks once. The patient understands.
        </h1>
        <p className="mt-3 text-muted-foreground text-pretty">
          Spoken discharge instructions in Kannada, Hindi, Tamil and English, and symptom reports
          that come back to the doctor in English.
        </p>
      </div>

      <nav aria-label="Choose your role" className="grid w-full max-w-3xl gap-4 sm:grid-cols-2">
        {ROLES.map(({ to, title, description, points, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            className="group rounded-xl outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >
            <Card className="h-full transition-all group-hover:-translate-y-0.5 group-hover:border-primary/40 group-hover:shadow-md">
              <CardHeader>
                <div className="mb-2 flex size-11 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                  <Icon className="size-6" />
                </div>
                <CardTitle className="flex items-center justify-between text-xl">
                  {title}
                  <ArrowRight className="size-5 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-primary" />
                </CardTitle>
                <CardDescription className="text-base">{description}</CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-1.5 text-sm text-muted-foreground">
                  {points.map((p) => (
                    <li key={p} className="flex items-center gap-2">
                      <span className="size-1.5 rounded-full bg-primary" aria-hidden />
                      {p}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </Link>
        ))}
      </nav>
    </div>
  );
}
