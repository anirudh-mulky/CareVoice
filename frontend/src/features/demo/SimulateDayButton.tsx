import { useQueryClient } from "@tanstack/react-query";
import { FastForward, Loader2 } from "lucide-react";
import { useState } from "react";
import type { AdvanceResult } from "@/shared/api/client";
import { Button } from "@/shared/ui/button";
import { advanceDay } from "./api";

function summary(result: AdvanceResult): string {
  if (result.patients.length === 0) return "No running care episodes.";
  const days = result.patients.map((p) => `${p.patient_name}: day ${p.recovery_day}`).join(" · ");
  const sent = result.reminders_sent;
  return `${days}. ${sent} reminder${sent === 1 ? "" : "s"} sent.`;
}

/** Demo only: move every running care episode one day on and send that day's reminders. */
export function SimulateDayButton() {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    try {
      setResult(summary(await advanceDay()));
      await queryClient.invalidateQueries();
    } catch {
      setResult("Could not simulate the next day (demo endpoints are off?).");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col items-start gap-1">
      <Button variant="outline" onClick={() => void run()} disabled={busy}>
        {busy ? <Loader2 className="animate-spin" aria-hidden /> : <FastForward aria-hidden />} Simulate next day
      </Button>
      {result && (
        <p role="status" className="text-sm text-muted-foreground">
          {result}
        </p>
      )}
    </div>
  );
}
