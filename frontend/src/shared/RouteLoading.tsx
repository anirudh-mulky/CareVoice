import { Loader2 } from "lucide-react";

/** Shown while the first screen's code downloads. No text, so it suits every language. */
export function RouteLoading() {
  return (
    <div role="status" aria-label="Loading" className="flex min-h-svh items-center justify-center">
      <Loader2 className="size-8 animate-spin text-primary" aria-hidden />
    </div>
  );
}
