import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.ai.tasks.extract_template.schema import Template as ExtractedTemplate


class Schema(BaseModel):
    # Responses always include defaulted fields, so generated TypeScript marks them required.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class Medicine(Schema):
    name: str
    dose: str | None = None
    frequency: str | None = None
    duration_days: int | None = None


class RedFlag(Schema):
    id: str
    label_en: str
    keywords: dict[str, list[str]] = Field(default_factory=dict)
    concepts: list[str] = Field(default_factory=list)


class MinorSymptom(Schema):
    id: str
    symptom_en: str
    remedy_en: str
    keywords: dict[str, list[str]] = Field(default_factory=dict)
    concepts: list[str] = Field(default_factory=list)


class Reminder(Schema):
    day: int = Field(ge=0)
    time: str = Field(pattern=r"^\d{2}:\d{2}$")
    message_en: str


class TemplateBody(Schema):
    name: str = Field(min_length=1, max_length=200)
    condition: str = Field(min_length=1, max_length=200)
    medicines: list[Medicine] = Field(default_factory=list)
    dos: list[str] = Field(default_factory=list)
    donts: list[str] = Field(default_factory=list)
    red_flags: list[RedFlag] = Field(min_length=1)
    minor_symptoms: list[MinorSymptom] = Field(default_factory=list)
    reminders: list[Reminder] = Field(default_factory=list)
    follow_up_day: int | None = Field(default=None, ge=0)


class TemplateSave(TemplateBody):
    """Omit id to create a template; give an existing id to save its next version."""

    id: uuid.UUID | None = None


class TemplateSummary(Schema):
    id: uuid.UUID
    version: int
    name: str
    condition: str
    medicines: int
    red_flags: int
    minor_symptoms: int
    languages: list[str]
    created_at: datetime


class TemplateOut(TemplateBody):
    id: uuid.UUID
    version: int
    versions: list[int]
    languages: list[str]
    translations: dict[str, dict[str, Any]] = Field(default_factory=dict)
    created_at: datetime


class TemplateExtractRequest(Schema):
    transcript: str = Field(min_length=1, max_length=5000)


class TemplateDraft(Schema):
    template: ExtractedTemplate
    source: str
    needs_review: bool
