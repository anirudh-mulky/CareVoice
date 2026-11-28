import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, Lock, MessageSquareReply, Send, ShieldCheck } from "lucide-react";
import { useRef, useState } from "react";
import { ApiError, type ReplyPreview, type ReportActions } from "@/shared/api/client";
import { useDebouncedCallback } from "@/shared/hooks/useDebouncedCallback";
import { LANGUAGES, isLang } from "@/shared/languages";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { VoiceInput } from "@/shared/VoiceInput";
import { alertHandled, approveRemedy, closeEpisode, getActions, previewReply, sendReply } from "./api";

const KIND_LABEL: Record<string, string> = {
  safety: "Automatic safety message",
  remedy: "Remedy from your template",
  doctor_reply: "Your reply",
};

const newKey = () => globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
const errorText = (err: unknown) => (err instanceof ApiError ? err.message : "Something went wrong. Try again.");

function RemedyPicker({ data, onDone }: { data: ReportActions; onDone: () => void }) {
  const [chosen, setChosen] = useState<string[]>(() =>
    data.remedy_options.filter((o) => o.suggested).map((o) => o.minor_id),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toggle = (id: string) => setChosen((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));

  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      await approveRemedy(data.report_id, chosen);
      onDone();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Remedy from your template</CardTitle>
        <p className="text-sm text-muted-foreground">
          Only your template's own remedies can be sent. The patient gets the verified translation shown below.
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <fieldset className="flex flex-col gap-3">
          <legend className="sr-only">Remedies to send</legend>
          {data.remedy_options.map((o) => (
            <label
              key={o.minor_id}
              className="flex cursor-pointer gap-3 rounded-lg border p-3 has-[:checked]:border-primary has-[:checked]:bg-primary/5"
            >
              <input
                type="checkbox"
                className="mt-1 size-4"
                checked={chosen.includes(o.minor_id)}
                onChange={() => toggle(o.minor_id)}
              />
              <span className="flex flex-col gap-1">
                <span className="font-medium">
                  {o.symptom_en} {o.suggested && <Badge variant="secondary">Matched</Badge>}
                </span>
                <span>{o.remedy_en}</span>
                <span className="text-sm text-muted-foreground" lang={data.language}>
                  Patient gets: {o.remedy_native}
                </span>
                {!o.translated && <span className="text-sm text-amber-800">No verified translation: sent in English</span>}
              </span>
            </label>
          ))}
        </fieldset>
        <Button size="lg" className="w-fit" disabled={busy || chosen.length === 0} onClick={() => void send()}>
          {busy ? <Loader2 className="animate-spin" aria-hidden /> : <Send aria-hidden />} Approve and send remedy
        </Button>
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function ReplyBox({ data, onDone }: { data: ReportActions; onDone: () => void }) {
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<ReplyPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = useRef(newKey());
  const language = isLang(data.language) ? LANGUAGES[data.language].label : data.language;

  const loadPreview = useDebouncedCallback(async (value: string) => {
    setPreview(value.trim() ? await previewReply(data.report_id, value).catch(() => null) : null);
  }, 400);

  const change = (value: string) => {
    setText(value);
    key.current = newKey();
    loadPreview.call(value);
  };

  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      await sendReply(data.report_id, text, key.current);
      setText("");
      setPreview(null);
      key.current = newKey();
      onDone();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageSquareReply className="size-5" aria-hidden /> Reply to the patient
        </CardTitle>
        <p className="text-sm text-muted-foreground">Type or dictate in English. The patient gets it in {language}.</p>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Quick replies">
          {data.quick_replies.map((q) => (
            <Button key={q.id} variant="outline" size="sm" onClick={() => change(q.text_en)}>
              {q.text_en}
            </Button>
          ))}
        </div>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">Your reply</span>
          <textarea
            value={text}
            onChange={(e) => change(e.target.value)}
            rows={3}
            className="rounded-md border bg-background px-3 py-2 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
          />
        </label>
        <details>
          <summary className="cursor-pointer text-sm text-muted-foreground">Dictate instead</summary>
          <div className="pt-3">
            <VoiceInput lang="en" record={false} onText={(spoken) => change(spoken)} />
          </div>
        </details>
        {preview && (
          <div
            aria-live="polite"
            className={preview.translated ? "rounded-lg bg-secondary p-3" : "rounded-lg bg-amber-50 p-3 text-amber-900"}
          >
            {preview.translated ? (
              <>
                <span className="block text-sm text-muted-foreground">Patient gets ({language})</span>
                <span lang={preview.language}>{preview.text_native}</span>
              </>
            ) : (
              <>No translation available in demo mode for this text: the patient will get it in English. Quick replies are translated.</>
            )}
          </div>
        )}
        <Button size="lg" className="w-fit" disabled={busy || !text.trim()} onClick={() => void send()}>
          {busy ? <Loader2 className="animate-spin" aria-hidden /> : <Send aria-hidden />} Send reply
        </Button>
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

/** What the doctor can do with a confirmed report: handle the alert, send a remedy, reply, close. */
export function ReportActionsPanel({ reportId }: { reportId: string }) {
  const queryClient = useQueryClient();
  const actions = useQuery({ queryKey: ["report-actions", reportId], queryFn: () => getActions(reportId) });
  const [confirmClose, setConfirmClose] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    for (const key of [["report-actions", reportId], ["report", reportId], ["reports"], ["discharges"]]) {
      void queryClient.invalidateQueries({ queryKey: key });
    }
  };
  const run = async (work: () => Promise<unknown>) => {
    setError(null);
    try {
      await work();
      refresh();
    } catch (err) {
      setError(errorText(err));
    }
  };

  if (!actions.data) return null;
  const data = actions.data;
  const closed = data.discharge_status === "closed";

  return (
    <div className="flex flex-col gap-5">
      {data.can_handle_alert && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border-2 border-red-300 bg-red-50 p-4">
          <p className="text-red-900">
            The patient was told to come to the hospital today. When you have spoken to them, mark the alert handled.
          </p>
          <Button variant="destructive" onClick={() => void run(() => alertHandled(data.discharge_id))}>
            <ShieldCheck aria-hidden /> Mark alert handled
          </Button>
        </div>
      )}

      {data.can_send_remedy && <RemedyPicker data={data} onDone={refresh} />}
      {data.report_type === "alert" && !closed && (
        <p className="text-sm text-muted-foreground">
          Remedies are not offered for alerts: please call the patient. You can still send a reply.
        </p>
      )}
      {!closed && <ReplyBox data={data} onDone={refresh} />}

      {data.sent.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Sent to the patient since this report</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-3" aria-label="Sent to the patient">
              {data.sent.map((m) => (
                <li key={m.id} className="flex gap-3">
                  <CheckCircle2 className="mt-1 size-5 shrink-0 text-emerald-600" aria-hidden />
                  <div>
                    <p className="text-sm font-medium">{KIND_LABEL[m.kind] ?? m.kind}</p>
                    <p lang={m.language}>{m.text_native}</p>
                    {m.text_en && m.text_en !== m.text_native && (
                      <p className="text-sm text-muted-foreground">{m.text_en}</p>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <div className="flex flex-wrap items-center gap-3 border-t pt-4">
        {closed ? (
          <p className="flex items-center gap-2 text-muted-foreground">
            <Lock className="size-4" aria-hidden /> This care episode is closed. The patient's links no longer work.
          </p>
        ) : confirmClose ? (
          <>
            <p>Close this care episode? The patient and carer links will stop working.</p>
            <Button variant="destructive" onClick={() => void run(() => closeEpisode(data.discharge_id))}>
              Yes, close it
            </Button>
            <Button variant="ghost" onClick={() => setConfirmClose(false)}>
              Cancel
            </Button>
          </>
        ) : (
          <Button variant="outline" onClick={() => setConfirmClose(true)}>
            <Lock aria-hidden /> Close care episode
          </Button>
        )}
      </div>
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
