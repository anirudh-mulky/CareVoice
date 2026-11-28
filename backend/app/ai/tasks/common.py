"""Template pieces shared by the AI tasks (shape of templates.red_flags / minor_symptoms)."""

from pydantic import BaseModel, Field


class FlagSpec(BaseModel):
    id: str
    label_en: str
    keywords: dict[str, list[str]] = Field(default_factory=dict)  # lang -> keywords
    concepts: list[str] = Field(default_factory=list)  # lexicon concept ids


class MinorSpec(BaseModel):
    id: str
    symptom_en: str
    remedy_en: str
    keywords: dict[str, list[str]] = Field(default_factory=dict)
    concepts: list[str] = Field(default_factory=list)


class TemplateRef(BaseModel):
    name: str
    condition: str
