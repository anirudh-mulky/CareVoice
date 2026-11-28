from pydantic import BaseModel, Field


class ExtractTemplateInput(BaseModel):
    transcript: str


class Medicine(BaseModel):
    name: str
    dose: str | None = None
    frequency: str | None = None
    duration_days: int | None = None


class RedFlag(BaseModel):
    id: str
    label_en: str


class MinorSymptom(BaseModel):
    id: str
    symptom_en: str
    remedy_en: str


class Reminder(BaseModel):
    day: int
    time: str
    message_en: str


class Template(BaseModel):
    name: str
    medicines: list[Medicine] = Field(default_factory=list)
    dos: list[str] = Field(default_factory=list)
    donts: list[str] = Field(default_factory=list)
    red_flags: list[RedFlag] = Field(default_factory=list)
    minor_symptoms: list[MinorSymptom] = Field(default_factory=list)
    reminders: list[Reminder] = Field(default_factory=list)
    follow_up_day: int | None = None
    unclear_fields: list[str] = Field(default_factory=list)
