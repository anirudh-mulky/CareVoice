import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.models import DischargeStatus, MessageKind, ReportStatus, ReportType


class Schema(BaseModel):
    # Responses always include defaulted fields, so generated TypeScript marks them required.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class RemedyOption(Schema):
    """One of the template's minor symptoms; its remedy is the only text that can be sent."""

    minor_id: str
    symptom_en: str
    remedy_en: str
    remedy_native: str  # what the patient will get
    translated: bool  # false -> no verified translation, the patient gets English
    suggested: bool  # matched in this report


class QuickReply(Schema):
    id: str
    text_en: str


class SentMessage(Schema):
    id: uuid.UUID
    kind: MessageKind
    text_native: str
    text_en: str | None
    language: str
    created_at: datetime


class ReportActions(Schema):
    report_id: uuid.UUID
    discharge_id: uuid.UUID
    report_type: ReportType
    report_status: ReportStatus
    discharge_status: DischargeStatus
    language: str
    can_send_remedy: bool  # never for alerts: those need a call, not a remedy
    can_handle_alert: bool
    can_close: bool
    remedy_options: list[RemedyOption] = Field(default_factory=list)
    quick_replies: list[QuickReply] = Field(default_factory=list)
    sent: list[SentMessage] = Field(default_factory=list)  # what the patient got since


class RemedyApproval(BaseModel):
    minor_ids: list[str] = Field(min_length=1, max_length=10)


class ReplyIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Write or say a reply")
        return value.strip()


class ReplyPreview(Schema):
    language: str
    text_native: str
    translated: bool  # false -> the patient will get the English text


class ActionResult(Schema):
    outcome: str  # "sent" | "already_sent" | "handled" | "closed"
    message: SentMessage | None = None
    discharge_status: DischargeStatus
    report_status: ReportStatus | None = None
