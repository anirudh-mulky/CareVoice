import { useCallback, useEffect, useRef } from "react";

/** Calls `fn` after `delay` ms of quiet; `flush()` runs a pending call now and awaits it. */
export function useDebouncedCallback<A extends unknown[]>(fn: (...args: A) => Promise<void>, delay: number) {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pending = useRef<A | null>(null);
  const latest = useRef(fn);
  useEffect(() => {
    latest.current = fn;
  });

  const flush = useCallback(async () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    const args = pending.current;
    pending.current = null;
    if (args) await latest.current(...args);
  }, []);

  const call = useCallback(
    (...args: A) => {
      pending.current = args;
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => void flush(), delay);
    },
    [delay, flush],
  );

  useEffect(() => () => void (timer.current && clearTimeout(timer.current)), []);
  return { call, flush };
}
