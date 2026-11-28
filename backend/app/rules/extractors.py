"""Rule-based extractors for doctor dictation (demo stand-ins for the LLM tasks).

extract_discharge: "Ramesh, 68, cataract right eye, standard template, diabetic so check
sugar daily, language Kannada." -> name, age, template, side, language, extras.
extract_template: a dictated care plan -> medicines, dos, don'ts, red flags, remedies.

Doses are never guessed: a medicine without a clear dose and frequency, or with an
ambiguous one ("5 or 10 mg"), goes into unclear_fields and blocks approval.
"""

import re

from app.ai.tasks.common import TemplateRef
from app.ai.tasks.extract_discharge.schema import Discharge, ExtractDischargeInput
from app.ai.tasks.extract_template.schema import (
    ExtractTemplateInput,
    Medicine,
    MinorSymptom,
    RedFlag,
    Reminder,
    Template,
)
from app.rules.lexicon import Lexicon, get_lexicon
from app.rules.text import normalise

SEP = " | "
_DOSE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg|ml|mcg|g|units?|iu|%|drops?|tablets?|tabs?|capsules?|caps?|puffs?)(?!\w)"
    r"|\b(?:one|two|three|four|half|a|1|2|3|4)\s+(?:drops?|tablets?|tabs?|capsules?|puffs?|teaspoons?|spoons?)\b"
)
_AMBIGUOUS = re.compile(r"\b\d+(?:\.\d+)?\s*(?:or|to|/)\s*\d+")
_TIMES = re.compile(
    r"\b(?:\d+|one|two|three|four|five|six)\s*times(?:\s+a\s+day|\s+daily)?\b|\bevery\s+\d+\s*hours?\b"
)
_LEADING_CONNECTORS = {"and", "also", "with", "plus", "then"}
_DURATION = re.compile(r"\bfor\s+(\d+)\s+(day|days|week|weeks)\b")
_PHONE = re.compile(
    r"(?:\b(?:son|daughter|husband|wife|carer|caretaker|father|mother|brother|sister)s?\s*"
    r"(?:phone|number|mobile)?\s*(?:is|number)?\s*)?(?:\+?91[\s-]*)?\b([6-9]\d{4}\s?\d{5})\b"
)
_NOT_AGE_AFTER = re.compile(
    r"\s*(?:mg|ml|mcg|g\b|%|drops?|times|days?|weeks?|tablets?|tabs?|units?|hours?|am|pm)"
)


def _words_re(words: list[str]) -> re.Pattern[str]:
    alts = sorted({re.escape(normalise(w)) for w in words if w.strip()}, key=len, reverse=True)
    return re.compile(r"(?<!\w)(?:" + "|".join(alts) + r")(?!\w)") if alts else re.compile(r"(?!)")


def _cut(text: str, start: int, end: int) -> str:
    return text[:start] + SEP + text[end:]


def medicine_issue(text: str, lex: Lexicon) -> bool:
    """True if this text names a medicine but its dose or frequency is unclear."""
    en = lex.pack("en")
    if not _words_re(sorted(en.words("medicine_words"))).search(text):
        return False
    has_dose = bool(_DOSE.search(text))
    has_freq = bool(
        _words_re(sorted(en.words("frequency_words"))).search(text) or _TIMES.search(text)
    )
    return _AMBIGUOUS.search(text) is not None or not (has_dose and has_freq)


def extract_discharge(data: ExtractDischargeInput, lexicon: Lexicon | None = None) -> Discharge:
    lex = lexicon or get_lexicon()
    en = lex.pack("en")
    work = normalise(data.transcript)
    out = Discharge()

    # Carer phone first, so its digits are never read as an age.
    if m := _PHONE.search(work):
        out.carer_phone = "+91" + m.group(1).replace(" ", "")
        work = _cut(work, m.start(), m.end())

    # Template: by name, condition or a spoken alias ("c section", "lscs").
    aliases: dict[str, TemplateRef] = {}
    alias_table: dict[str, list[str]] = en.data.get("template_aliases", {}) or {}
    for tpl in data.templates:
        for alias in [tpl.name, tpl.condition, *alias_table.get(tpl.condition, [])]:
            aliases[normalise(alias)] = tpl
    found: list[TemplateRef] = []
    pattern = _words_re(list(aliases))
    for m in reversed(list(pattern.finditer(work))):
        tpl = aliases[m.group(0)]
        if tpl not in found:
            found.append(tpl)
        work = _cut(work, m.start(), m.end())
    if len(found) == 1:
        out.template_name = found[0].name

    # Side: "right eye", "left", "both eyes".
    sides: dict[str, list[str]] = en.data.get("sides", {}) or {}
    for side, words in sides.items():
        if m := _words_re(
            [*words, *(f"{w} eye" for w in words), *(f"{w} eyes" for w in words)]
        ).search(work):
            out.side = side  # type: ignore[assignment]
            work = _cut(work, m.start(), m.end())
            break

    # Language: "language Kannada", "in Hindi", or just the name.
    names = lex.language_names()
    lang_re = re.compile(
        r"(?:(?<!\w)(?:language|in)\s+)?(?<!\w)(" + "|".join(map(re.escape, names)) + r")(?!\w)"
    )
    if m := lang_re.search(work):
        out.language = names[m.group(1)]
        work = _cut(work, m.start(), m.end())

    # Age: "68", "68 years", "age 68"; not a dose ("5 mg") or a day count.
    for m in re.finditer(r"(?:\bage\s*)?\b(\d{1,3})\b(\s*(?:years?\s*old|years?|yrs?|yo))?", work):
        value = int(m.group(1))
        if not 0 < value <= 120 or (not m.group(2) and _NOT_AGE_AFTER.match(work, m.end())):
            continue
        out.age = value
        work = _cut(work, m.start(), m.end())
        break

    # Name: the first words, e.g. "Ramesh" or "patient Lakshmi".
    filler = en.words("filler")
    m = re.match(
        r"\s*(?:(?:patient|name is|name)\s+)?"
        r"([^\W\d_][^\s,.;|\d]*(?:\s+[^\W\d_][^\s,.;|\d]*){0,2})",
        work,
    )
    if m:
        words = []
        for w in m.group(1).split():
            if w in filler or _words_re(sorted(en.words("medicine_words"))).fullmatch(w):
                break
            words.append(w)
        if words:
            out.patient_name = " ".join(w.capitalize() for w in words)
            work = work[: m.start(1)] + SEP + work[m.start(1) + len(" ".join(words)) :]

    # Whatever is left are the doctor's extra instructions.
    for piece in re.split(r"[|,.;]+", work):
        piece = piece.strip(" -")
        tokens = piece.split()
        while tokens and tokens[0] in _LEADING_CONNECTORS:
            tokens.pop(0)
        if not tokens or all(t in filler for t in tokens):
            continue
        text = " ".join(tokens)
        out.extra_instructions.append(text[0].upper() + text[1:])

    for field in ("patient_name", "age", "template_name", "language"):
        if getattr(out, field) is None:
            out.unclear_fields.append(field)
    for i, extra in enumerate(out.extra_instructions):
        if medicine_issue(normalise(extra), lex):
            out.unclear_fields.append(f"extra_instructions[{i}]")
    return out


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalise(text)).strip("_")[:40]


def _cap(text: str) -> str:
    text = text.strip(" ,")
    return text[:1].upper() + text[1:]


def extract_template(data: ExtractTemplateInput, lexicon: Lexicon | None = None) -> Template:
    lex = lexicon or get_lexicon()
    en = lex.pack("en")
    medicine_re = _words_re(sorted(en.words("medicine_words")))
    freq_re = _words_re(sorted(en.words("frequency_words")))
    sentences = [s.strip() for s in re.split(r"[.;\n]+|\bthen\b", data.transcript) if s.strip()]
    out = Template(name="")

    if sentences:
        first = normalise(sentences[0])
        m = re.search(
            r"(?:template (?:for|called|named)|this is the|this is)\s+(.+?)(?:\s+template)?$", first
        )
        if m:
            out.name = _cap(m.group(1))
            sentences = sentences[1:]

    for original in sentences:
        s = normalise(original)
        if m := re.search(r"(?:follow\s?up|review|check\s?up)\D{0,25}?day\s*(\d+)", s) or re.search(
            r"(?:follow\s?up|review|check\s?up).*?after\s+(\d+)\s+days", s
        ):
            out.follow_up_day = int(m.group(1))
            continue
        if m := re.match(
            r"(?:on\s+)?day\s+(\d+)(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?\s*,?\s*"
            r"(?:remind(?:\s+(?:them|the patient|her|him))?(?:\s+to)?|reminder)\s+(.+)",
            s,
        ):
            hour = int(m.group(2)) if m.group(2) else 9
            if m.group(4) == "pm" and hour < 12:
                hour += 12
            elif m.group(4) == "am" and hour == 12:
                hour = 0
            out.reminders.append(
                Reminder(
                    day=int(m.group(1)),
                    time=f"{hour:02d}:{m.group(3) or '00'}",
                    message_en=_cap(m.group(5)),
                )
            )
            continue
        if m := re.match(
            r"(?:come back|return|visit (?:the )?hospital|call(?: us)?"
            r"|red flags?|danger signs?|emergency)\b"
            r".*?(?:\bif\b|:|\bare\b|\bis\b)\s+(.+)",
            s,
        ):
            for item in re.split(r",|\bor\b|\band\b", m.group(1)):
                item = re.sub(
                    r"^(?:there (?:is|are)|they have|she has|he has|any|an?)\s+", "", item.strip()
                )
                if item:
                    out.red_flags.append(RedFlag(id=f"rf_{_slug(item)}", label_en=_cap(item)))
            continue
        if m := re.match(
            r"if\s+(?:there is\s+|they have\s+|she has\s+|he has\s+)?(.+?),?\s+"
            r"(?:then\s+|tell them to\s+|they should\s+|ask them to\s+)(.+)",
            s,
        ):
            out.minor_symptoms.append(
                MinorSymptom(
                    id=f"ms_{_slug(m.group(1))}",
                    symptom_en=_cap(m.group(1)),
                    remedy_en=_cap(m.group(2)),
                )
            )
            continue
        if re.match(r"(?:do not|dont|avoid|never|no)\b", s):
            out.donts.append(_cap(original))
            continue
        if medicine_re.search(s):
            i = len(out.medicines)
            dose = _DOSE.search(s)
            freq = _TIMES.search(s) or freq_re.search(s)
            duration = _DURATION.search(s)
            name = re.split(r"\d|\b(?:one|two|half|a)\s+(?:drop|tablet)", s, maxsplit=1)[0]
            name = re.sub(r"^(?:give|take|use|prescribe|start|put)\s+", "", name).strip()
            days = None
            if duration:
                days = int(duration.group(1)) * (7 if duration.group(2).startswith("week") else 1)
            out.medicines.append(
                Medicine(
                    name=_cap(name) or _cap(s),
                    dose=dose.group(0) if dose and not _AMBIGUOUS.search(s) else None,
                    frequency=freq.group(0) if freq else None,
                    duration_days=days,
                )
            )
            if out.medicines[i].dose is None:
                out.unclear_fields.append(f"medicines[{i}].dose")
            if out.medicines[i].frequency is None:
                out.unclear_fields.append(f"medicines[{i}].frequency")
            continue
        out.dos.append(_cap(original))

    if not out.name:
        out.unclear_fields.insert(0, "name")
    if not out.red_flags:
        out.unclear_fields.append("red_flags")
    return out
