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

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-svh flex-col">
      <header className="mx-auto flex w-full max-w-5xl items-center justify-between px-5 py-4">
        <Logo />
        <ModeBadge />
      </header>
      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-5">{children}</main>
      <footer className="mx-auto w-full max-w-5xl px-5 py-6 text-center text-xs text-muted-foreground">
        This app does not replace your doctor. In an emergency, go to the nearest hospital.
      </footer>
    </div>
  );
}
