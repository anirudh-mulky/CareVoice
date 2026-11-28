"""Demo translator: looks up pre-translated phrases, never invents a translation.

Phrases come from data (demo_phrases.json) and can be added at runtime, e.g. from the
verified template translations. Anything not found comes back unchanged, so the
English (or original) wording is kept and the doctor sees both sides.
"""

import json
import re
import unicodedata
from pathlib import Path

PHRASES_FILE = Path(__file__).with_name("demo_phrases.json")


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold().strip()
    text = re.sub(r"[\s]+", " ", text)
    return text.rstrip(".!?।")


class DemoTranslator:
    name = "demo"

    def __init__(self, phrases_file: Path | None = PHRASES_FILE) -> None:
        # (normalised text, language) -> phrase id ; (phrase id, language) -> text
        self._index: dict[tuple[str, str], str] = {}
        self._texts: dict[tuple[str, str], str] = {}
        if phrases_file is not None:
            for phrase_id, by_lang in json.loads(phrases_file.read_text("utf-8")).items():
                for lang, text in by_lang.items():
                    self.add(phrase_id, lang, text)

    def add(self, phrase_id: str, lang: str, text: str) -> None:
        """Register one language's wording of a phrase. Same id = same meaning."""
        self._texts[(phrase_id, lang)] = text
        self._index[(normalise(text), lang)] = phrase_id

    def lookup(self, text: str, src: str, dst: str) -> str | None:
        phrase_id = self._index.get((normalise(text), src))
        if phrase_id is None:
            return None
        return self._texts.get((phrase_id, dst))

    async def translate(self, text: str, src: str, dst: str) -> str:
        if src == dst or not text.strip():
            return text
        return self.lookup(text, src, dst) or text
