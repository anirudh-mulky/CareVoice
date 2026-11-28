import type { ReportListItem } from "@/shared/api/client";
import { cn } from "@/shared/lib/utils";

const STYLES: Record<ReportListItem["type"], { label: string; className: string }> = {
  alert: { label: "Alert", className: "bg-red-600 text-white" },
  minor: { label: "Minor", className: "bg-amber-100 text-amber-900" },
  general: { label: "Question", className: "bg-sky-100 text-sky-900" },
};

export function ReportTypeBadge({ type }: { type: ReportListItem["type"] }) {
  const style = STYLES[type];
  return (
    <span className={cn("inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold", style.className)}>
      {style.label}
    </span>
  );
}
