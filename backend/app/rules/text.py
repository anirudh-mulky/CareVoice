"""Text normalisation and keyword matching for Indian-language and code-mixed speech.

- English keywords match whole words plus simple endings ("pain" -> "painful").
- Kannada/Hindi/Tamil keywords (native script or romanised) match as stems, because
  these languages add suffixes: "kempu" matches "kempagide", "ಕೆಂಪು" matches "ಕೆಂಪಾಗಿದೆ".
- Every language's keywords are tried on every transcript, so code-mixed speech
  ("wound se paani aa raha hai", "eye red aagide") and a wrongly detected language still match.
"""

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

EN_SUFFIXES = ("", "s", "es", "ing", "ed", "ness", "y", "ful", "ly")
LATIN_VOWELS = "aeiou"
MIN_LATIN_STEM = 4  # "vali" stays "vali" so it does not also match "valathu" (right side)
MIN_NATIVE_STEM = 3

_PUNCT = re.compile(r"[,.;:!?।॥|\n\r\t\"“”()\[\]{}/]+")
_APOSTROPHES = re.compile(r"[’'`´]")
_JOINERS = re.compile(r"[-_‐–—]")


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold()
    text = _APOSTROPHES.sub("", text)
    text = _JOINERS.sub(" ", text)
    text = text.replace("़", "")  # Devanagari nukta: ज़ == ज
    text = text.replace("ँ", "ं")  # chandrabindu == anusvara: हाँ == हां
    return re.sub(r"\s+", " ", text).strip()


def tokens_of(text: str) -> list[str]:
    return normalise(_PUNCT.sub(" ", text)).split()


def clauses_of(text: str, breakers: Iterable[str] = ()) -> list[list[str]]:
    """Split into clauses on punctuation and contrast words ("but", "lekin", "aadre")."""
    breaker_set = {normalise(b) for b in breakers}
    clauses: list[list[str]] = []
    for chunk in _PUNCT.split(normalise(text)):
        current: list[str] = []
        for token in chunk.split():
            if token in breaker_set:
                if current:
                    clauses.append(current)
                current = []
            else:
                current.append(token)
        if current:
            clauses.append(current)
    return clauses


def _is_latin(text: str) -> bool:
    return all(ord(ch) < 0x250 for ch in text)


def _stem(word: str) -> str:
    if _is_latin(word):
        stem = word
        while len(stem) > MIN_LATIN_STEM and stem[-1] in LATIN_VOWELS:
            stem = stem[:-1]
        return stem
    stem = word
    while len(stem) > MIN_NATIVE_STEM and unicodedata.category(stem[-1]) in ("Mn", "Mc"):
        stem = stem[:-1]
    return stem


@dataclass(frozen=True)
class TokenPattern:
    word: str
    english: bool

    def matches(self, token: str) -> bool:
        if self.english:
            return any(token == self.word + suffix for suffix in EN_SUFFIXES)
        return token.startswith(self.word) or token.startswith(_stem(self.word))


@dataclass(frozen=True)
class Keyword:
    text: str  # normalised keyword
    language: str
    patterns: tuple[TokenPattern, ...]

    @classmethod
    def build(cls, raw: str, language: str) -> "Keyword":
        text = normalise(_PUNCT.sub(" ", raw))
        english = language == "en" and _is_latin(text)
        return cls(text, language, tuple(TokenPattern(w, english) for w in text.split()))

    def find(self, clause: list[str]) -> list[tuple[int, int]]:
        """All (start, end) token spans in the clause where this keyword occurs."""
        n = len(self.patterns)
        spans = []
        for i in range(len(clause) - n + 1):
            if all(p.matches(clause[i + j]) for j, p in enumerate(self.patterns)):
                spans.append((i, i + n))
        return spans


@dataclass(frozen=True)
class Hit:
    keyword: Keyword
    clause: int
    start: int
    end: int
    negated: bool

    def overlaps(self, other: "Hit") -> bool:
        return self.clause == other.clause and self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class NegationRules:
    before: frozenset[str]
    after: frozenset[str]
    suffixes: tuple[str, ...]
    blockers: frozenset[str]
    window: int = 2

    def is_negated(self, clause: list[str], start: int, end: int, keyword: Keyword) -> bool:
        # "no pain": negation word just before, unless a blocker sits between ("not much pain").
        before = clause[max(0, start - self.window) : start]
        for i, token in enumerate(before):
            if token in self.before and not any(t in self.blockers for t in before[i + 1 :]):
                return True
        # "novu illa", "dard nahi": negation word just after, unless a blocker comes first
        # ("dard kam nahi ho raha" = the pain is NOT reducing, which must still escalate).
        after = clause[end : end + self.window]
        for i, token in enumerate(after):
            if token in self.after and not any(t in self.blockers for t in after[:i]):
                return True
        # "valikkala": negation fused onto the word itself.
        last = clause[end - 1]
        own_last = keyword.text.split()[-1]
        return any(last.endswith(s) and not own_last.endswith(s) for s in self.suffixes)


def find_hits(
    keywords: Iterable[Keyword], clauses: list[list[str]], negation: NegationRules
) -> list[Hit]:
    hits = []
    for keyword in keywords:
        for c, clause in enumerate(clauses):
            for start, end in keyword.find(clause):
                negated = negation.is_negated(clause, start, end, keyword)
                hits.append(Hit(keyword, c, start, end, negated))
    return hits


def near(
    clause: list[str], start: int, end: int, words: frozenset[str], window: int = 2
) -> str | None:
    """The first of `words` within `window` tokens around a span, e.g. an intensifier."""
    lo, hi = max(0, start - window), min(len(clause), end + window)
    for token in clause[lo:start] + clause[end:hi]:
        if token in words:
            return token
    return None
