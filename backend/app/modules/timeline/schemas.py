import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.models import ActorType, DischargeStatus


class Schema(BaseModel):
    # Responses always include defaulted fields, so generated TypeScript marks them required.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class TimelineEntry(Schema):
    id: uuid.UUID
    at: datetime
    type: str  # the event type, e.g. "report.confirmed"
    actor: ActorType
    title: str  # plain English, e.g. "Patient confirmed a report (alert)"
    detail: str | None = None  # e.g. the English text of a message
    tone: str = "neutral"  # neutral | good | warning | danger
    report_id: uuid.UUID | None = None


class Timeline(Schema):
    discharge_id: uuid.UUID
    patient_name: str
    status: DischargeStatus
    entries: list[TimelineEntry]
