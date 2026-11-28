import { useQueryClient } from "@tanstack/react-query";
import { Loader2, RotateCcw } from "lucide-react";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "@/shared/api/client";
import { Button } from "@/shared/ui/button";
import { resetDemo } from "./api";

const CONFIRM =
  "Reset the demo? Every discharge, message and report made since the start is removed and the seeded patients (Ramesh, Sunita, Murugan) come back.";

/** Demo only: restore the seeded data so the flow can be shown again from the start. */
export function ResetDemoButton() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const run = async () => {
    if (!window.confirm(CONFIRM)) return;
    setBusy(true);
    setNote(null);
    try {
      await resetDemo();
      // Pages for one discharge or report point at ids that no longer exist after a reset.
      if (pathname.startsWith("/doctor/")) navigate("/doctor");
      await queryClient.invalidateQueries();
      setNote("Demo data restored.");
    } catch (err) {
      setNote(
        err instanceof ApiError && err.status === 404
          ? "Reset is turned off on this server."
          : "Could not reset the demo. Try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      {note && (
        <p role="status" className="text-sm text-muted-foreground">
          {note}
        </p>
      )}
      <Button variant="outline" size="sm" onClick={() => void run()} disabled={busy}>
        {busy ? <Loader2 className="animate-spin" aria-hidden /> : <RotateCcw aria-hidden />} Reset demo
      </Button>
    </div>
  );
}
