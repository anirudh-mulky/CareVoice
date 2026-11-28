import type { DischargeOut } from "@/shared/api/client";
import { cn } from "@/shared/lib/utils";

const STYLES: Record<DischargeOut["status"], { label: string; className: string }> = {
  alert: { label: "Alert", className: "bg-red-600 text-white" },
  needs_followup: { label: "Needs follow-up", className: "bg-amber-100 text-amber-900" },
  sent: { label: "Sent", className: "bg-sky-100 text-sky-900" },
  understood: { label: "Understood", className: "bg-emerald-100 text-emerald-900" },
  draft: { label: "Draft", className: "bg-muted text-muted-foreground" },
  closed: { label: "Closed", className: "bg-muted text-muted-foreground" },
};

export function StatusBadge({ status }: { status: DischargeOut["status"] }) {
  const style = STYLES[status];
  return (
    <span className={cn("inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold", style.className)}>
      {style.label}
    </span>
  );
}
