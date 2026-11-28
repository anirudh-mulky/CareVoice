import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, Mic, RotateCcw, Send } from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, type DischargeCard, type DischargeOut, type ExtractResponse } from "@/shared/api/client";
import { useDebouncedCallback } from "@/shared/hooks/useDebouncedCallback";
import { LANGUAGES, isLang } from "@/shared/languages";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { VoiceInput } from "@/shared/VoiceInput";
import { approveDischarge, createDraft, dischargeTemplates, extractDischarge, updateDraft } from "./api";
import { DischargeCardForm } from "./DischargeCardForm";
import { PatientLinks } from "./PatientLinks";

const EXAMPLE = "Ramesh, 68, cataract right eye, standard template, diabetic so check sugar daily, language Kannada.";

type Phase = "dictate" | "review" | "sent";
type Busy = "extracting" | "saving" | "approving" | null;

function newKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
}

function unclearFrom(err: unknown): string[] | null {
  if (err instanceof ApiError && err.details && typeof err.details === "object" && "unclear_fields" in err.details) {
    const fields = (err.details as { unclear_fields: unknown }).unclear_fields;
    return Array.isArray(fields) ? fields.map(String) : null;
  }
  return null;
}

/** Doctor dictates one sentence -> editable card -> fix anything yellow -> Approve. */
export function NewDischargePage() {
  const queryClient = useQueryClient();
  const templates = useQuery({ queryKey: ["discharge-templates"], queryFn: dischargeTemplates });

  const [phase, setPhase] = useState<Phase>("dictate");
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState<string | null>(null);
  const [extracted, setExtracted] = useState<ExtractResponse | null>(null);
  const [card, setCard] = useState<DischargeCard | null>(null);
  const [unclear, setUnclear] = useState<string[]>([]);
  const [draftId, setDraftId] = useState<string | null>(null);
  const [sent, setSent] = useState<DischargeOut | null>(null);
  const approveKey = useRef(newKey());
  const draftRef = useRef<string | null>(null);

  const applyServer = (out: DischargeOut) => {
    draftRef.current = out.id;
    setDraftId(out.id);
    setUnclear(out.unclear_fields);
  };

  /** Save the card: create the draft once it has a name and template, then update it. */
  const save = async (next: DischargeCard) => {
    setBusy("saving");
    setError(null);
    try {
      if (draftRef.current) applyServer(await updateDraft(draftRef.current, next));
      else if (next.patient_name && next.template_id) applyServer(await createDraft(next));
    } catch (err) {
      const fields = unclearFrom(err);
      if (fields) setUnclear(fields);
      else setError(err instanceof Error ? err.message : "Could not save");
    } finally {
      setBusy(null);
    }
  };
  const debouncedSave = useDebouncedCallback(save, 600);

  const onDictated = async (text: string) => {
    setBusy("extracting");
    setError(null);
    try {
      const result = await extractDischarge(text);
      setExtracted(result);
      setCard(result.card);
      setUnclear(result.unclear_fields);
      setPhase("review");
      setBusy(null);
      draftRef.current = null;
      setDraftId(null);
      approveKey.current = newKey();
      await save(result.card); // the server's check replaces the extractor's list
    } catch (err) {
      setBusy(null);
      setError(err instanceof Error ? err.message : "Could not read that. Try again or type it.");
    }
  };

  const onEdit = (next: DischargeCard) => {
    setCard(next);
    debouncedSave.call(next);
  };

  const approve = async () => {
    await debouncedSave.flush();
    if (!draftRef.current) return;
    setBusy("approving");
    setError(null);
    try {
      const result = await approveDischarge(draftRef.current, approveKey.current);
      setSent(result.discharge);
      setPhase("sent");
      void queryClient.invalidateQueries({ queryKey: ["discharges"] });
    } catch (err) {
      const fields = unclearFrom(err);
      if (fields) setUnclear(fields);
      else setError(err instanceof Error ? err.message : "Could not approve");
    } finally {
      setBusy(null);
    }
  };

  const restart = () => {
    setPhase("dictate");
    setCard(null);
    setExtracted(null);
    setUnclear([]);
    setDraftId(null);
    draftRef.current = null;
    setSent(null);
    setError(null);
  };

  if (phase === "sent" && sent) {
    const lang = sent.patient.preferred_language;
    return (
      <Card className="mx-auto w-full max-w-xl text-center">
        <CardContent className="flex flex-col items-center gap-4 py-6">
          <CheckCircle2 className="size-14 text-primary" aria-hidden />
          <h1 className="text-2xl font-semibold">Discharge approved</h1>
          <p className="text-muted-foreground">
            {sent.patient.name}'s care card was sent in {isLang(lang) ? LANGUAGES[lang].label : lang} to the patient and
            their carer.
          </p>
          <PatientLinks dischargeId={sent.id} />
          <div className="flex flex-wrap justify-center gap-2">
            <Button onClick={restart} size="lg">
              <Mic /> Discharge another patient
            </Button>
            <Button asChild variant="outline" size="lg">
              <Link to="/doctor">Back to patients</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const blocked = unclear.length > 0;
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">New discharge</h1>
        <p className="text-muted-foreground">Say one sentence. Check the card. Approve.</p>
      </div>

      {phase === "dictate" && (
        <Card>
          <CardHeader className="text-center">
            <CardTitle>Tap the mic and dictate</CardTitle>
            <CardDescription className="mx-auto max-w-lg">
              For example: “{EXAMPLE}”
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-4">
            {busy === "extracting" ? (
              <p className="flex items-center gap-2 py-12 text-lg">
                <Loader2 className="size-5 animate-spin" aria-hidden /> Reading your dictation…
              </p>
            ) : (
              <VoiceInput lang="en" onText={(text) => void onDictated(text)} />
            )}
          </CardContent>
        </Card>
      )}

      {phase === "review" && card && (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle>Discharge card</CardTitle>
                <CardDescription className="mt-1 italic">“{extracted?.transcript}”</CardDescription>
              </div>
              <div className="flex flex-wrap gap-2">
                {extracted?.matched_patient && <Badge variant="secondary">Existing patient</Badge>}
                {extracted?.needs_review && <Badge variant="destructive">Needs review</Badge>}
                <Button variant="outline" size="sm" onClick={restart}>
                  <RotateCcw /> Dictate again
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            <DischargeCardForm card={card} unclear={unclear} templates={templates.data ?? []} onChange={onEdit} />

            <div className="flex flex-col items-start gap-2 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
              <p role="status" aria-live="polite" className="text-sm">
                {busy === "saving" ? (
                  <span className="text-muted-foreground">Saving…</span>
                ) : blocked ? (
                  <span className="font-medium text-amber-900">
                    {unclear.length === 1 ? "1 field needs" : `${unclear.length} fields need`} checking before you can
                    approve.
                  </span>
                ) : draftId ? (
                  <span className="text-muted-foreground">Ready. Nothing reaches the patient until you approve.</span>
                ) : (
                  <span className="text-muted-foreground">Add a name and template to save the draft.</span>
                )}
              </p>
              <Button size="lg" onClick={() => void approve()} disabled={blocked || !draftId || busy !== null}>
                {busy === "approving" ? <Loader2 className="animate-spin" aria-hidden /> : <Send aria-hidden />}
                Approve and send
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-4 py-3 text-red-900">
          {error}
        </p>
      )}
    </div>
  );
}
