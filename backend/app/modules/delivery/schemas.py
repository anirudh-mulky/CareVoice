import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.models import ActorType, DischargeStatus, MessageDirection, MessageKind


class Schema(BaseModel):
    # Responses always include defaulted fields, so generated TypeScript marks them required.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class CareMedicine(Schema):
    name: str
    instructions: str


class CareExtra(Schema):
    text: str
    translated: bool


class CardLabels(Schema):
    medicines: str
    do: str
    dont: str
    extras: str


class CareCard(Schema):
    """The care card in the patient's language, red flags first."""

    language: str  # the language the card is shown in
    translated: bool  # false -> no verified translation yet, shown in English
    title: str
    greeting: str
    red_flags_title: str
    red_flags: list[str]
    medicines: list[CareMedicine] = Field(default_factory=list)
    dos: list[str] = Field(default_factory=list)
    donts: list[str] = Field(default_factory=list)
    extras: list[CareExtra] = Field(default_factory=list)
    follow_up: str | None = None
    labels: CardLabels


class Viewer(Schema):
    type: ActorType  # patient or carer
    name: str


class HospitalInfo(Schema):
    name: str
    phone: str | None


class PatientHome(Schema):
    patient_name: str
    viewer: Viewer
    language: str  # the care card's language (English when no verified translation)
    ui_language: str  # the viewer's chosen language, for buttons, voice and messages
    hospital: HospitalInfo
    status: DischargeStatus
    recovery_day: int
    card: CareCard


class ChatMessage(Schema):
    id: uuid.UUID
    direction: MessageDirection
    kind: MessageKind
    text: str
    text_en: str | None
    language: str
    audio_url: str | None
    played_at: datetime | None
    created_at: datetime


class PatientLink(Schema):
    recipient_type: ActorType
    name: str
    relation: str | None = None
    language: str
    url: str


class DemoPatientLink(Schema):
    patient_name: str
    template_name: str
    language: str
    status: DischargeStatus
    links: list[PatientLink]


class LanguageChange(BaseModel):
    """Tap a language (language="hi") or say it (spoken="Hindi" / "ಹಿಂದಿ")."""

    language: str | None = None
    spoken: str | None = Field(default=None, max_length=100)


class LanguageOut(Schema):
    language: str
