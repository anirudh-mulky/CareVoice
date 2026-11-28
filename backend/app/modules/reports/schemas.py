import uuid
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.models import ActorType, DischargeStatus, ReportStatus, ReportType


class Schema(BaseModel):
    # Responses always include defaulted fields, so generated TypeScript marks them required.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


# --- Patient side -----------------------------------------------------------------------


# Big symptom buttons shown after two failed tries (spec: error handling). Lexicon concepts.
SYMPTOM_ICONS = ("pain", "redness", "bleeding", "fever", "swelling", "vision_loss", "wound_problem")


class ReportIn(BaseModel):
    """What the patient said (speech-to-text or typed), or the symptom icons they tapped."""

    transcript: str = Field(default="", max_length=2000)
    icons: list[str] = Field(default_factory=list, max_length=len(SYMPTOM_ICONS))
    language: str | None = None  # defaults to the patient's language
    stt_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("icons")
    @classmethod
    def known_icons(cls, value: list[str]) -> list[str]:
        unknown = [i for i in value if i not in SYMPTOM_ICONS]
        if unknown:
            raise ValueError(f"Unknown symptom icons: {unknown}")
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def something_said(self) -> "ReportIn":
        self.transcript = self.transcript.strip()
        if not self.transcript and not self.icons:
            raise ValueError("Say or type what is wrong, or tap a symptom")
        return self


class ReadBack(Schema):
    report_id: uuid.UUID
    language: str  # the language of the read-back (what the patient spoke, if detectable)
    read_back: str  # "You said: very red and pain. Is that right?" in the patient's language
    # Set when the patient spoke a different language from their setting: offer to switch.
    suggested_language: str | None = None


class ConfirmIn(BaseModel):
    """Yes/no by button (answer) or by voice (transcript)."""

    answer: bool | None = None
    transcript: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def one_of(self) -> "ConfirmIn":
        if self.answer is None and not (self.transcript or "").strip():
            raise ValueError("Give an answer or a spoken transcript")
        return self


class ConfirmOutcome(StrEnum):
    sent = "sent"  # yes: the English report is on the doctor's dashboard
    say_again = "say_again"  # no: the patient tells it again
    unclear = "unclear"  # could not tell yes from no: tap a button


class ConfirmOut(Schema):
    report_id: uuid.UUID
    outcome: ConfirmOutcome
    message: str  # in the patient's language


# --- Doctor side ------------------------------------------------------------------------


class SymptomOut(Schema):
    name_en: str
    body_part: str | None = None
    severity_words: str | None = None
    onset: str | None = None
    duration: str | None = None


class FlagOut(Schema):
    id: str
    label_en: str


class MinorOut(Schema):
    id: str
    symptom_en: str


class RemedyOut(Schema):
    minor_id: str
    remedy_en: str  # always the template's own text


class MedicineOut(Schema):
    name: str
    instructions: str


class ReportListItem(Schema):
    id: uuid.UUID
    discharge_id: uuid.UUID
    patient_name: str
    language: str
    type: ReportType
    status: ReportStatus
    reported_by: ActorType
    summary_en: str
    recovery_day: int | None
    created_at: datetime


class ReportDetail(ReportListItem):
    patient_age: int | None
    template_name: str
    discharge_status: DischargeStatus
    transcript_native: str
    translation_en: str | None
    read_back_native: str | None
    stt_confidence: float | None
    audio_url: str | None
    confidence: str | None
    reasons: list[str] = Field(default_factory=list)
    needs_review: bool
    symptoms: list[SymptomOut] = Field(default_factory=list)
    red_flags: list[FlagOut] = Field(default_factory=list)
    minor_symptoms: list[MinorOut] = Field(default_factory=list)
    suggested_remedies: list[RemedyOut] = Field(default_factory=list)
    medicines: list[MedicineOut] = Field(default_factory=list)
    extra_instructions: list[str] = Field(default_factory=list)


class ReportUpdate(BaseModel):
    status: Literal[ReportStatus.seen]
