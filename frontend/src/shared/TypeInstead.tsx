import { Keyboard, Send } from "lucide-react";
import { type FormEvent, useId, useState } from "react";
import { useI18n } from "./i18n";
import type { Lang } from "./languages";
import { Button } from "./ui/button";

type TypeInsteadProps = {
  lang?: Lang;
  onSubmit: (text: string) => void;
  defaultOpen?: boolean;
  /** Open it from outside, e.g. when the mic is unsupported. */
  open?: boolean;
};

/** Small fallback on every voice step, so the flow works without a mic or browser speech. */
export function TypeInstead({ lang, onSubmit, defaultOpen = false, open }: TypeInsteadProps) {
  const { t } = useI18n(lang);
  const [isOpen, setOpen] = useState(defaultOpen);
  const [text, setText] = useState("");
  const id = useId();
  const shown = open ?? isOpen;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const value = text.trim();
    if (!value) return;
    onSubmit(value);
    setText("");
  };

  if (!shown) {
    return (
      <Button type="button" variant="link" size="sm" onClick={() => setOpen(true)} className="text-muted-foreground">
        <Keyboard /> {t("type_instead.open")}
      </Button>
    );
  }
  return (
    <form onSubmit={submit} className="flex w-full max-w-md items-end gap-2">
      <label htmlFor={id} className="sr-only">
        {t("type_instead.placeholder")}
      </label>
      <textarea
        id={id}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={t("type_instead.placeholder")}
        rows={2}
        lang={lang}
        className="min-h-11 flex-1 resize-none rounded-md border bg-background px-3 py-2 text-base outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) submit(e);
        }}
      />
      <Button type="submit" size="lg" disabled={!text.trim()}>
        <Send /> {t("type_instead.send")}
      </Button>
    </form>
  );
}
