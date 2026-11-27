import { useQuery } from "@tanstack/react-query";
import { getHealth } from "@/shared/api/client";
import { Badge } from "@/shared/ui/badge";

/** Shows whether the server runs in demo mode (no keys) or with real providers. */
export function ModeBadge() {
  const { data, isError } = useQuery({ queryKey: ["health"], queryFn: getHealth });

  if (isError) {
    return (
      <Badge variant="destructive" role="status">
        Server unreachable
      </Badge>
    );
  }
  if (!data) return null;
  return (
    <Badge variant={data.mode === "demo" ? "secondary" : "default"} role="status">
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {data.mode === "demo" ? "Demo mode · no keys needed" : "Live providers"}
    </Badge>
  );
}
