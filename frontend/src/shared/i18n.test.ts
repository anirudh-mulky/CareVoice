import { MESSAGES, translate } from "./i18n";
import { LANG_CODES } from "./languages";

const english = Object.keys(MESSAGES.en).sort();

test.each(LANG_CODES)("%s has every UI string", (lang) => {
  expect(Object.keys(MESSAGES[lang]).sort()).toEqual(english);
});

test.each(LANG_CODES)("%s keeps every {placeholder}", (lang) => {
  for (const [key, text] of Object.entries(MESSAGES.en)) {
    const placeholders = text.match(/\{\w+\}/g) ?? [];
    for (const p of placeholders) {
      expect(MESSAGES[lang][key as keyof typeof MESSAGES.en]).toContain(p);
    }
  }
});

test("fills placeholders and translates", () => {
  expect(translate("en", "mic.time_left", { seconds: 5 })).toBe("5 seconds left");
  expect(translate("kn", "mic.time_left", { seconds: 5 })).toBe("ಇನ್ನೂ 5 ಸೆಕೆಂಡ್");
  expect(translate("hi", "common.call_hospital")).toBe("अस्पताल को फ़ोन करें");
});

test("leaves unknown placeholders visible rather than blank", () => {
  expect(translate("en", "mic.time_left")).toBe("{seconds} seconds left");
});
