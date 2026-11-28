import { useQuery } from "@tanstack/react-query";
import { Check, Copy, ExternalLink } from "lucide-react";
import { useState } from "react";
import type { PatientLink } from "@/shared/api/client";
import { LANGUAGES, isLang } from "@/shared/languages";
import { Button } from "@/shared/ui/button";
import { shareLinks } from "./api";

function LinkRow({ link }: { link: PatientLink }) {
  const [copied, setCopied] = useState(false);
  const full = `${window.location.origin}${link.url}`;
  const who = link.recipient_type === "patient" ? `${link.name} (patient)` : `${link.name} (${link.relation ?? "carer"})`;
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2">
      <span className="text-sm">
        <span className="font-medium">{who}</span>{" "}
        <span className="text-muted-foreground">· {isLang(link.language) ? LANGUAGES[link.language].label : link.language}</span>
      </span>
      <span className="flex gap-2">
        <Button asChild size="sm" variant={link.recipient_type === "patient" ? "default" : "outline"}>
          <a href={link.url} target="_blank" rel="noreferrer">
            <ExternalLink aria-hidden /> Open {link.recipient_type === "patient" ? "patient" : "carer"} link
          </a>
        </Button>
        <Button
          size="sm"
          variant="ghost"
          aria-label={`Copy ${who} link`}
          onClick={() =>
            void navigator.clipboard?.writeText(full).then(() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            })
          }
        >
          {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
        </Button>
      </span>
    </li>
  );
}

/** Links the hospital sends to the patient and carers (WhatsApp/SMS in production). */
export function PatientLinks({ dischargeId }: { dischargeId: string }) {
  const links = useQuery({
    queryKey: ["links", dischargeId],
    queryFn: () => shareLinks(dischargeId),
    staleTime: Number.POSITIVE_INFINITY,
  });
  if (links.isPending) return <p className="text-sm text-muted-foreground">Preparing links…</p>;
  if (links.isError) return <p className="text-sm text-destructive">Could not create links.</p>;
  return (
    <ul className="flex w-full flex-col gap-2 text-left">
      {links.data.map((l) => (
        <LinkRow key={l.url} link={l} />
      ))}
    </ul>
  );
}
