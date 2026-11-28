"""Rule-based symptom analyser (demo stand-in for the analyse_symptom LLM task).

Matches the patient's words against their own template's red flags and minor symptoms,
in every language at once, ignoring negated symptoms ("novu illa"). Any symptom it
recognises but cannot place in the template lowers confidence, which escalates to the
doctor: when unsure, never reassure.
"""

import re

from app.ai.tasks.analyse_symptom.schema import (
    AnalyseSymptomInput,
    SuggestedRemedy,
    Symptom,
    SymptomItem,
)
from app.rules.lexicon import Lexicon, get_lexicon
from app.rules.text import Hit, clauses_of, find_hits, near, normalise


def _duration(text: str, units: frozenset[str]) -> str | None:
    for match in re.finditer(r"(\d+)\s+(\S+)", normalise(text)):
        if match.group(2) in units:
            return f"{match.group(1)} {match.group(2)}"
    return None


def analyse_symptom(data: AnalyseSymptomInput, lexicon: Lexicon | None = None) -> Symptom:
    lex = lexicon or get_lexicon()
    pack = lex.pack(data.language)
    text = " . ".join(t for t in (data.transcript_native, data.transcript_en) if t)
    clauses = clauses_of(text, lex.clause_breakers)

    def live(hits: list[Hit]) -> list[Hit]:
        return [h for h in hits if not h.negated]

    flag_hits: dict[str, list[Hit]] = {}
    for flag in data.red_flags:
        hits = live(
            find_hits(lex.keywords_for(flag.keywords, flag.concepts), clauses, lex.negation)
        )
        if hits:
            flag_hits[flag.id] = hits

    minor_hits: dict[str, list[Hit]] = {}
    for minor in data.minor_symptoms:
        hits = live(
            find_hits(lex.keywords_for(minor.keywords, minor.concepts), clauses, lex.negation)
        )
        if hits:
            minor_hits[minor.id] = hits

    placed = [h for hits in (*flag_hits.values(), *minor_hits.values()) for h in hits]

    concept_hits: dict[str, list[Hit]] = {}
    for concept in lex.concepts.values():
        hits = live(find_hits(concept.keywords, clauses, lex.negation))
        if hits:
            concept_hits[concept.id] = hits

    unexplained = [
        cid
        for cid, hits in concept_hits.items()
        if not any(h.overlaps(p) for h in hits for p in placed)
    ]

    onset = next((t for c in clauses for t in c if t in lex.onset_words), None)
    duration = _duration(text, lex.duration_units)

    symptoms: list[SymptomItem] = []
    native_items: list[str] = []
    # In the order the patient said them, so the read-back sounds natural.
    spoken_order = sorted(
        concept_hits.items(), key=lambda kv: min((h.clause, h.start) for h in kv[1])
    )
    for cid, hits in spoken_order:
        concept = lex.concepts[cid]
        first = hits[0]
        clause = clauses[first.clause]
        severity = near(clause, first.start, first.end, lex.intensifiers) or near(
            clause, first.start, first.end, lex.mild
        )
        symptoms.append(
            SymptomItem(
                name_en=concept.label("en"),
                body_part=concept.body_part,
                severity_words=severity,
                onset=onset,
                duration=duration,
            )
        )
        label = concept.label(pack.code)
        if severity in lex.intensifiers:
            label = f"{pack.text('very')} {label}".strip()
        native_items.append(label)

    # Flags matched only through the template's own keywords still need a symptom line.
    all_concept_hits = [c for hits in concept_hits.values() for c in hits]
    for flag in data.red_flags:
        hits = flag_hits.get(flag.id, [])
        if hits and not any(h.overlaps(c) for h in hits for c in all_concept_hits):
            symptoms.append(SymptomItem(name_en=flag.label_en, onset=onset, duration=duration))
            native_items.append(flag.label_en)

    has_text = bool(normalise(text).strip(" ."))
    confidence = "low" if unexplained or not has_text else "high"

    remedies = {m.id: m.remedy_en for m in data.minor_symptoms}
    matched_minors = list(minor_hits)

    if symptoms:
        names = ", ".join(s.name_en for s in symptoms)
        summary = f"Patient reports {names}"
        severities = sorted({s.severity_words for s in symptoms if s.severity_words})
        if severities:
            summary += f" (described as: {', '.join(severities)})"
        if data.recovery_day:
            summary += f" on recovery day {data.recovery_day}"
        summary += "."
        joiner = f" {pack.text('joiner', 'and')} "
        read_back = pack.text("read_back").format(items=joiner.join(native_items))
    else:
        quoted = (data.transcript_en or data.transcript_native).strip()
        summary = f'Patient says: "{quoted}". No listed symptom was recognised.'
        read_back = pack.text("read_back_general")

    return Symptom(
        summary_en=summary,
        read_back_native=read_back,
        symptoms=symptoms,
        matched_flag_ids=list(flag_hits),
        matched_minor_ids=matched_minors,
        suggested_remedies=[
            SuggestedRemedy(minor_id=mid, remedy_en=remedies[mid]) for mid in matched_minors
        ],
        confidence=confidence,
    )
