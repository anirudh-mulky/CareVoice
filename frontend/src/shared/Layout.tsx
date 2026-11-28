import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ModeBadge } from "@/shared/ModeBadge";

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight">
      <img src="/favicon.svg" alt="" className="size-7" />
      <span className="text-lg">CareVoice</span>
    </Link>
  );
}

/** Staff and demo shell. `actions` sit in the header beside the mode badge (e.g. demo reset). */
export function Layout({ children, actions }: { children: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex min-h-svh flex-col">
      <header className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-3 px-5 py-4">
        <Logo />
        <div className="flex flex-wrap items-center justify-end gap-3">
          {actions}
          <ModeBadge />
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-5">{children}</main>
      <footer className="mx-auto w-full max-w-5xl px-5 py-6 text-center text-xs text-muted-foreground">
        This app does not replace your doctor. In an emergency, go to the nearest hospital.
      </footer>
    </div>
  );
}
