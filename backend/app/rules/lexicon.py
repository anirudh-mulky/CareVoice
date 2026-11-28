"""Loads app/rules/lexicons/<lang>.yaml. Adding a language = adding a file."""

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.rules.text import Keyword, NegationRules, normalise

LEXICON_DIR = Path(__file__).with_name("lexicons")


@dataclass
class Concept:
    id: str
    body_part: str | None = None
    labels: dict[str, str] = field(default_factory=dict)  # lang -> label
    keywords: list[Keyword] = field(default_factory=list)

    def label(self, lang: str) -> str:
        return self.labels.get(lang) or self.labels.get("en") or self.id


@dataclass
class LanguagePack:
    code: str
    data: dict[str, Any]

    def words(self, key: str) -> set[str]:
        return {normalise(str(w)) for w in self.data.get(key, []) or []}

    def text(self, key: str, default: str = "") -> str:
        return str(self.data.get(key, default))


@dataclass
class Lexicon:
    languages: dict[str, LanguagePack]
    concepts: dict[str, Concept]
    negation: NegationRules
    clause_breakers: frozenset[str]
    intensifiers: frozenset[str]
    mild: frozenset[str]
    onset_words: frozenset[str]
    duration_units: frozenset[str]

    def pack(self, lang: str) -> LanguagePack:
        """Language pack for 'kn', 'kn-IN' or 'kn-Latn'; English if unknown."""
        base = lang.split("-")[0].lower()
        return self.languages.get(base) or self.languages["en"]

    def all_words(self, key: str) -> frozenset[str]:
        out: set[str] = set()
        for pack in self.languages.values():
            out |= pack.words(key)
        return frozenset(out)

    def language_names(self) -> dict[str, str]:
        """Spoken language name -> code, e.g. {'kannada': 'kn', 'ಕನ್ನಡ': 'kn'}."""
        return {name: code for code, pack in self.languages.items() for name in pack.words("names")}

    def keywords_for(
        self, keywords: dict[str, list[str]] | None, concepts: list[str] | None
    ) -> list[Keyword]:
        """A template item's own keywords (every language) plus its concepts' keywords."""
        out = [Keyword.build(k, lang) for lang, words in (keywords or {}).items() for k in words]
        for concept_id in concepts or []:
            concept = self.concepts.get(concept_id)
            if concept is not None:
                out.extend(concept.keywords)
        return out


def _check_words(node: Any, where: str) -> None:
    """YAML reads unquoted yes/no/on/off as booleans; a word list must hold only text."""
    if isinstance(node, dict):
        for key, value in node.items():
            if not isinstance(key, str):
                raise ValueError(f"{where}: key {key!r} is not text; quote it")
            _check_words(value, f"{where}:{key}")
    elif isinstance(node, list):
        for item in node:
            if not isinstance(item, str):
                raise ValueError(f"{where}: {item!r} is not text; quote it in the YAML")


def load_lexicon(directory: Path = LEXICON_DIR) -> Lexicon:
    languages: dict[str, LanguagePack] = {}
    concepts: dict[str, Concept] = {}
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text("utf-8")) or {}
        _check_words(data, path.name)
        code = str(data.get("language", path.stem))
        languages[code] = LanguagePack(code, data)
        for concept_id, spec in (data.get("concepts") or {}).items():
            concept = concepts.setdefault(concept_id, Concept(concept_id))
            if spec.get("body_part"):
                concept.body_part = spec["body_part"]
            if spec.get("label"):
                concept.labels[code] = str(spec["label"])
            concept.keywords.extend(Keyword.build(str(k), code) for k in spec.get("keywords", []))
    if "en" not in languages:
        raise ValueError("lexicons must include en.yaml")

    def merged(key: str) -> frozenset[str]:
        out: set[str] = set()
        for pack in languages.values():
            out |= pack.words(key)
        return frozenset(out)

    suffixes: set[str] = set()
    for pack in languages.values():
        suffixes |= pack.words("negation_suffixes")

    return Lexicon(
        languages=languages,
        concepts=concepts,
        negation=NegationRules(
            before=merged("negation_before"),
            after=merged("negation_after"),
            suffixes=tuple(sorted(suffixes, key=len, reverse=True)),
            blockers=merged("negation_blockers"),
        ),
        clause_breakers=merged("clause_breakers"),
        intensifiers=merged("intensifiers"),
        mild=merged("mild"),
        onset_words=merged("onset_words"),
        duration_units=merged("duration_units"),
    )


@lru_cache
def get_lexicon() -> Lexicon:
    return load_lexicon()
