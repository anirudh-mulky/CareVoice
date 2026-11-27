import { ArrowLeft } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { Button } from "@/shared/ui/button";

/** Placeholder for screens that later build parts add. Never a blank page. */
export function NotBuiltYetPage() {
  const { pathname } = useLocation();
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 py-16 text-center">
      <h1 className="text-2xl font-semibold">This screen is on its way</h1>
      <p className="max-w-md text-muted-foreground">
        <code className="rounded bg-muted px-1.5 py-0.5 text-sm">{pathname}</code> is not built yet. Head
        back to choose your role.
      </p>
      <Button asChild variant="outline">
        <Link to="/">
          <ArrowLeft /> Back to start
        </Link>
      </Button>
    </div>
  );
}
