"""Decision rules applied in code, never by the LLM (spec: "Decision rules").

- Any red-flag match, low confidence, or STT confidence under the threshold -> alert.
- Minor match only, confidence high -> minor, with remedies copied from the template by id
  (any remedy text from the analyser or an LLM is ignored).
- Nothing matched -> general: the doctor replies.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from app.ai.tasks.analyse_symptom.schema import SuggestedRemedy, Symptom
from app.ai.tasks.common import MinorSpec


class ReportKind(StrEnum):
    alert = "alert"
    minor = "minor"
    general = "general"


@dataclass(frozen=True)
class Decision:
    type: ReportKind
    remedies: list[SuggestedRemedy] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def decide(
    symptom: Symptom,
    template_minors: list[MinorSpec],
    stt_confidence: float | None,
    stt_threshold: float = 0.6,
) -> Decision:
    reasons = []
    if symptom.matched_flag_ids:
        reasons.append("red_flag")
    if symptom.confidence == "low":
        reasons.append("low_confidence")
    if stt_confidence is not None and stt_confidence < stt_threshold:
        reasons.append("low_stt_confidence")
    if reasons:
        return Decision(ReportKind.alert, reasons=reasons)

    template_remedies = {m.id: m.remedy_en for m in template_minors}
    remedies = [
        SuggestedRemedy(minor_id=mid, remedy_en=template_remedies[mid])
        for mid in symptom.matched_minor_ids
        if mid in template_remedies  # an id the template does not have is dropped
    ]
    if remedies:
        return Decision(ReportKind.minor, remedies=remedies, reasons=["minor_match"])
    return Decision(ReportKind.general, reasons=["no_match"])
