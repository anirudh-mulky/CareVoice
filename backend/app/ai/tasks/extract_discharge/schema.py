from typing import Literal

from pydantic import BaseModel, Field

from app.ai.tasks.common import TemplateRef


class ExtractDischargeInput(BaseModel):
    transcript: str
    templates: list[TemplateRef]


class Discharge(BaseModel):
    patient_name: str | None = None
    age: int | None = Field(default=None, ge=0, le=120)
    template_name: str | None = None
    side: Literal["right", "left", "both"] | None = None
    extra_instructions: list[str] = Field(default_factory=list)
    language: str | None = None  # code: kn, hi, ta, en
    carer_phone: str | None = None
    unclear_fields: list[str] = Field(default_factory=list)
