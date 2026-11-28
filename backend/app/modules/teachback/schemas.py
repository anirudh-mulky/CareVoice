from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.models import DischargeStatus


class Schema(BaseModel):
    # Responses always include defaulted fields, so generated TypeScript marks them required.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class Outcome(StrEnum):
    understood = "understood"  # enough warning signs named: done
    try_again = "try_again"  # missed signs were re-explained; one more try
    needs_followup = "needs_followup"  # out of tries: the care team follows up


class TeachbackAnswer(BaseModel):
    """What the patient said (browser speech-to-text in demo mode, or typed)."""

    transcript: str = Field(min_length=1, max_length=2000)
    language: str | None = None  # defaults to the patient's language
    stt_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("transcript")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Say or type an answer")
        return value.strip()


class FlagItem(Schema):
    id: str
    label: str  # in the patient's language when a verified translation exists


class TeachbackResult(Schema):
    try_number: int
    max_tries: int
    outcome: Outcome
    passed: bool
    mentioned: list[FlagItem] = Field(default_factory=list)  # all tries so far
    missed: list[FlagItem] = Field(default_factory=list)
    reply: str  # spoken back to the patient, in their language
    discharge_status: DischargeStatus


class TeachbackState(Schema):
    language: str
    question: str
    complete: bool
    tries_used: int
    max_tries: int
    discharge_status: DischargeStatus
    last: TeachbackResult | None = None
