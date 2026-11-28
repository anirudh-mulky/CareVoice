import { Plus, X } from "lucide-react";
import type { ReactNode } from "react";
import type { DischargeCard, TemplateOption } from "@/shared/api/client";
import { LANG_CODES, LANGUAGES } from "@/shared/languages";
import { cn } from "@/shared/lib/utils";
import { Button } from "@/shared/ui/button";
import { unclearReason } from "./unclear";

type Props = {
  card: DischargeCard;
  unclear: string[];
  templates: TemplateOption[];
  onChange: (card: DischargeCard) => void;
};

const input =
  "h-11 w-full rounded-md border bg-background px-3 text-base outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50";

/** One field; yellow with a reason when the server says it is unclear. */
function Field({ id, label, field, unclear, children, className }: {
  id: string;
  label: string;
  field: string;
  unclear: string[];
  children: ReactNode;
  className?: string;
}) {
  const flagged = unclear.includes(field);
  return (
    <div
      data-unclear={flagged || undefined}
      className={cn("flex flex-col gap-1.5 rounded-lg p-2", flagged && "bg-amber-100 ring-2 ring-amber-400", className)}
    >
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      {children}
      {flagged && (
        <p id={`${id}-why`} className="text-sm font-medium text-amber-900">
          {unclearReason(field)}
        </p>
      )}
    </div>
  );
}

/** The editable discharge card. Every change goes to the server, which decides what is unclear. */
export function DischargeCardForm({ card, unclear, templates, onChange }: Props) {
  const set = <K extends keyof DischargeCard>(key: K, value: DischargeCard[K]) => onChange({ ...card, [key]: value });
  const extras = card.extra_instructions ?? [];
  const setExtra = (i: number, value: string) => set("extra_instructions", extras.map((e, j) => (j === i ? value : e)));

  return (
    <div className="grid gap-2 sm:grid-cols-6">
      <Field id="patient_name" label="Patient name" field="patient_name" unclear={unclear} className="sm:col-span-4">
        <input
          id="patient_name"
          className={input}
          value={card.patient_name ?? ""}
          onChange={(e) => set("patient_name", e.target.value || null)}
          aria-invalid={unclear.includes("patient_name")}
        />
      </Field>
      <Field id="age" label="Age" field="age" unclear={unclear} className="sm:col-span-2">
        <input
          id="age"
          type="number"
          min={0}
          max={120}
          inputMode="numeric"
          className={input}
          value={card.age ?? ""}
          onChange={(e) => set("age", e.target.value === "" ? null : Number(e.target.value))}
          aria-invalid={unclear.includes("age")}
        />
      </Field>
      <Field id="template" label="Template" field="template_name" unclear={unclear} className="sm:col-span-3">
        <select
          id="template"
          className={input}
          value={card.template_id ?? ""}
          onChange={(e) => {
            const t = templates.find((o) => o.id === e.target.value);
            onChange({ ...card, template_id: t?.id ?? null, template_name: t?.name ?? null });
          }}
          aria-invalid={unclear.includes("template_name")}
        >
          <option value="">Choose…</option>
          {templates.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </Field>
      <Field id="side" label="Side" field="side" unclear={unclear} className="sm:col-span-3">
        <select
          id="side"
          className={input}
          value={card.side ?? ""}
          onChange={(e) => set("side", (e.target.value || null) as DischargeCard["side"])}
        >
          <option value="">Not applicable</option>
          <option value="right">Right</option>
          <option value="left">Left</option>
          <option value="both">Both</option>
        </select>
      </Field>
      <Field id="language" label="Patient's language" field="language" unclear={unclear} className="sm:col-span-3">
        <select
          id="language"
          className={input}
          value={card.language ?? ""}
          onChange={(e) => set("language", e.target.value || null)}
          aria-invalid={unclear.includes("language")}
        >
          <option value="">Choose…</option>
          {LANG_CODES.map((code) => (
            <option key={code} value={code}>
              {LANGUAGES[code].label}
            </option>
          ))}
        </select>
      </Field>
      <Field id="carer_phone" label="Carer's phone (optional)" field="carer_phone" unclear={unclear} className="sm:col-span-3">
        <input
          id="carer_phone"
          type="tel"
          inputMode="tel"
          className={input}
          value={card.carer_phone ?? ""}
          placeholder="+91 98450 12345"
          onChange={(e) => set("carer_phone", e.target.value || null)}
          aria-invalid={unclear.includes("carer_phone")}
        />
      </Field>

      <div className="flex flex-col gap-2 sm:col-span-6">
        <p className="px-2 text-sm font-medium">Extra instructions for this patient</p>
        {extras.length === 0 && <p className="px-2 text-sm text-muted-foreground">None: the template covers it.</p>}
        {extras.map((extra, i) => (
          <Field
            key={i}
            id={`extra-${i}`}
            label={`Instruction ${i + 1}`}
            field={`extra_instructions[${i}]`}
            unclear={unclear}
          >
            <div className="flex gap-2">
              <input
                id={`extra-${i}`}
                className={input}
                value={extra}
                onChange={(e) => setExtra(i, e.target.value)}
                aria-invalid={unclear.includes(`extra_instructions[${i}]`)}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`Remove instruction ${i + 1}`}
                onClick={() => set("extra_instructions", extras.filter((_, j) => j !== i))}
              >
                <X />
              </Button>
            </div>
          </Field>
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="ml-2 w-fit"
          onClick={() => set("extra_instructions", [...extras, ""])}
        >
          <Plus /> Add instruction
        </Button>
      </div>
    </div>
  );
}
