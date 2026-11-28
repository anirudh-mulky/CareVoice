import { createContext, type ReactNode, useCallback, useContext, useMemo, useState } from "react";
import en from "@/i18n/en.json";
import hi from "@/i18n/hi.json";
import kn from "@/i18n/kn.json";
import ta from "@/i18n/ta.json";
import { isLang, type Lang } from "./languages";

export type MessageKey = keyof typeof en;
type Messages = Record<MessageKey, string>;

export const MESSAGES: Record<Lang, Partial<Messages>> = { en, kn, hi, ta };

/** Look up a UI string in a language, falling back to English, and fill {placeholders}. */
export function translate(
  lang: Lang,
  key: MessageKey,
  vars: Record<string, string | number> = {},
): string {
  const template = MESSAGES[lang][key] ?? en[key] ?? key;
  return template.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? `{${name}}`));
}

type I18n = {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: MessageKey, vars?: Record<string, string | number>) => string;
};

const I18nContext = createContext<I18n | null>(null);
const STORAGE_KEY = "carevoice.lang";

function initialLang(fallback: Lang): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && isLang(saved)) return saved;
  } catch {
    // storage blocked (private mode): use the fallback
  }
  return fallback;
}

export function I18nProvider({ children, defaultLang = "en" }: { children: ReactNode; defaultLang?: Lang }) {
  const [lang, setLangState] = useState<Lang>(() => initialLang(defaultLang));
  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // ignore
    }
  }, []);
  const value = useMemo<I18n>(
    () => ({ lang, setLang, t: (key, vars) => translate(lang, key, vars) }),
    [lang, setLang],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

/** UI strings in the current language. A `lang` override renders one widget in another language. */
export function useI18n(override?: Lang): I18n {
  const ctx = useContext(I18nContext);
  const lang = override ?? ctx?.lang ?? "en";
  return useMemo(
    () => ({
      lang,
      setLang: ctx?.setLang ?? (() => {}),
      t: (key, vars) => translate(lang, key, vars),
    }),
    [lang, ctx?.setLang],
  );
}
