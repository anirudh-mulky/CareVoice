from typing import Literal

from pydantic import BaseModel, Field

from app.ai.tasks.common import FlagSpec, MinorSpec


class AnalyseSymptomInput(BaseModel):
    transcript_native: str
    transcript_en: str | None = None
    language: str
    red_flags: list[FlagSpec]
    minor_symptoms: list[MinorSpec]
    recovery_day: int | None = None
    medicines: list[str] = Field(default_factory=list)


class SymptomItem(BaseModel):
    name_en: str
    body_part: str | None = None
    severity_words: str | None = None
    onset: str | None = None
    duration: str | None = None


class SuggestedRemedy(BaseModel):
    minor_id: str
    remedy_en: str


class Symptom(BaseModel):
    summary_en: str
    read_back_native: str
    symptoms: list[SymptomItem] = Field(default_factory=list)
    matched_flag_ids: list[str] = Field(default_factory=list)
    matched_minor_ids: list[str] = Field(default_factory=list)
    suggested_remedies: list[SuggestedRemedy] = Field(default_factory=list)
    confidence: Literal["high", "low"]
