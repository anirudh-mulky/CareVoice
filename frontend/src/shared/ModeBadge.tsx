import { useQuery } from "@tanstack/react-query";
import { KeyRound } from "lucide-react";
import { getHealth, getSystemStatus } from "@/shared/api/client";
import { Badge } from "@/shared/ui/badge";

/**
 * Staff header badge: demo mode (no keys), live providers, or "Key not set" when a real provider
 * was asked for without its key and the app fell back to demo for it.
 */
export function ModeBadge() {
  const health = useQuery({ queryKey: ["health"], queryFn: getHealth });
  const status = useQuery({ queryKey: ["system-status"], queryFn: getSystemStatus, staleTime: 60_000 });

  if (health.isError) {
    return (
      <Badge variant="destructive" role="status">
        Server unreachable
      </Badge>
    );
  }

  // The badge sits on the main screen: an odd status reply must never break the page.
  const providers = Array.isArray(status.data?.providers) ? status.data.providers : [];
  const missing = providers.filter((p) => p.status === "key_not_set");
  if (status.data?.key_not_set || missing.length > 0) {
    const which = missing.map((p) => `${p.kind} (${p.requested})`).join(", ");
    return (
      <Badge
        variant="outline"
        role="status"
        className="border-amber-300 bg-amber-50 text-amber-900"
        title={which ? `No key for: ${which}` : undefined}
      >
        <KeyRound aria-hidden /> Key not set, using demo mode
      </Badge>
    );
  }

  if (!health.data) return null;
  // PROVIDER_MODE=real with every provider still on browser/demo is, in practice, demo mode.
  const live =
    health.data.mode === "real" && (providers.length === 0 || providers.some((p) => p.mode === "real"));
  return (
    <Badge variant={live ? "default" : "secondary"} role="status">
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {live ? "Live providers" : "Demo mode · no keys needed"}
    </Badge>
  );
}
