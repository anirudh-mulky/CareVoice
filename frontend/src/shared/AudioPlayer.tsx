import { Loader2, RotateCcw, Square, Volume2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/shared/lib/utils";
import { useI18n } from "./i18n";
import { LANGUAGES, isLang, type Lang } from "./languages";
import { speak, stopSpeaking } from "./speech";
import { useVoiceServices } from "./voiceServices";
import { Button } from "./ui/button";

type AudioPlayerProps = {
  /** What is said, in `lang`. Spoken by the browser when there is no audio file (demo mode). */
  text: string;
  lang: Lang;
  /** Provider audio (real mode). */
  src?: string | null;
  autoPlay?: boolean;
  onPlayed?: () => void;
  className?: string;
};

type State = "idle" | "loading" | "playing";

/** Replayable voice note: plays provider audio if present, otherwise speaks the text. */
export function AudioPlayer({ text, lang, src, autoPlay = false, onPlayed, className }: AudioPlayerProps) {
  const { t } = useI18n(lang);
  const [state, setState] = useState<State>("idle");
  const [plays, setPlays] = useState(0);
  const [noVoice, setNoVoice] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  const services = useVoiceServices();

  const stop = () => {
    audio.current?.pause();
    stopSpeaking();
    setState("idle");
  };

  const play = async () => {
    stop();
    setNoVoice(false);
    let url = src ?? null;
    let made = false;
    if (!url && services.speak) {
      // Real mode: the server's Indian-language voice (cached), else the browser below.
      setState("loading");
      try {
        url = URL.createObjectURL(await services.speak(text, lang));
        made = true;
      } catch {
        url = null;
      }
    }
    if (url) {
      const el = audio.current ?? new Audio();
      audio.current = el;
      el.src = url;
      el.onended = () => {
        setState("idle");
        if (made && url) URL.revokeObjectURL(url);
      };
      setState("loading");
      try {
        await el.play();
        setState("playing");
        setPlays((n) => n + 1);
        onPlayed?.();
        return;
      } catch {
        // Fall through to browser speech.
      }
    }
    setState("loading");
    const result = await speak(text, lang, {
      onStart: () => {
        setState("playing");
        setPlays((n) => n + 1);
        onPlayed?.();
      },
    });
    setState("idle");
    if (!result.spoken && result.reason !== "stopped") setNoVoice(true);
  };

  useEffect(() => {
    if (!autoPlay) return stop;
    const id = setTimeout(() => void play(), 0);
    return () => {
      clearTimeout(id);
      stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- play once per message
  }, [autoPlay, src, text, lang]);

  const label = state === "playing" ? t("player.stop") : plays > 0 ? t("player.replay") : t("player.play");
  const Icon = state === "loading" ? Loader2 : state === "playing" ? Square : plays > 0 ? RotateCcw : Volume2;

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <Button
        type="button"
        size="lg"
        variant={state === "playing" ? "secondary" : "default"}
        onClick={() => (state === "playing" ? stop() : void play())}
        aria-label={label}
        className="w-fit"
      >
        <Icon className={cn(state === "loading" && "animate-spin")} aria-hidden />
        {state === "playing" ? t("player.speaking") : label}
      </Button>
      {noVoice && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("player.no_voice", { language: isLang(lang) ? LANGUAGES[lang].label : lang })}
        </p>
      )}
    </div>
  );
}
