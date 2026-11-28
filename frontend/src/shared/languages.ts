/** Languages CareVoice speaks. Adding one = a row here + src/i18n/<code>.json + a backend lexicon. */
export const LANGUAGES = {
  en: { label: "English", speech: "en-IN" },
  kn: { label: "ಕನ್ನಡ", speech: "kn-IN" },
  hi: { label: "हिंदी", speech: "hi-IN" },
  ta: { label: "தமிழ்", speech: "ta-IN" },
} as const;

export type Lang = keyof typeof LANGUAGES;

export const LANG_CODES = Object.keys(LANGUAGES) as Lang[];

export function isLang(value: string): value is Lang {
  return value in LANGUAGES;
}

/** "kn" -> "kn-IN" for the Web Speech API; unknown codes fall back to Indian English. */
export function speechCode(lang: string): string {
  const base = lang.split("-")[0]?.toLowerCase() ?? "en";
  return isLang(base) ? LANGUAGES[base].speech : LANGUAGES.en.speech;
}
