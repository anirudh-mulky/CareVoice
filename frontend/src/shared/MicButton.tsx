import { Loader2, Mic, Square } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import type { CaptureStatus } from "./useVoiceCapture";

type MicButtonProps = {
  status: CaptureStatus;
  onPress: () => void;
  /** 0..1 live input level, used to grow the ring while listening. */
  level?: number;
  label: string;
  disabled?: boolean;
  size?: "md" | "lg";
  className?: string;
};

/** The big mic. Pulses while listening; one tap to start, one tap to stop. */
export function MicButton({ status, onPress, level = 0, label, disabled, size = "lg", className }: MicButtonProps) {
  const listening = status === "listening";
  const processing = status === "processing";
  const dim = size === "lg" ? "size-28" : "size-20";
  const icon = size === "lg" ? "size-12" : "size-9";
  return (
    <div className={cn("relative inline-flex items-center justify-center", className)}>
      {listening && (
        <>
          <span aria-hidden className={cn("absolute rounded-full bg-red-500/25 animate-ping", dim)} />
          <span
            aria-hidden
            className={cn("absolute rounded-full bg-red-500/20 transition-transform duration-100", dim)}
            style={{ transform: `scale(${1.1 + level * 0.6})` }}
          />
        </>
      )}
      <button
        type="button"
        onClick={onPress}
        disabled={disabled || processing}
        aria-pressed={listening}
        aria-label={label}
        className={cn(
          "relative flex items-center justify-center rounded-full text-white shadow-lg transition-all",
          "outline-none focus-visible:ring-4 focus-visible:ring-ring/50 disabled:opacity-60",
          dim,
          listening ? "bg-red-600 hover:bg-red-700" : "bg-primary hover:bg-primary/90 active:scale-95",
        )}
      >
        {processing ? (
          <Loader2 className={cn(icon, "animate-spin")} aria-hidden />
        ) : listening ? (
          <Square className={cn(icon, "fill-current")} aria-hidden />
        ) : (
          <Mic className={icon} aria-hidden />
        )}
      </button>
    </div>
  );
}
