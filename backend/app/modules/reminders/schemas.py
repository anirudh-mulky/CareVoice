import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.core.models import JobStatus


class Schema(BaseModel):
    # Responses always include defaulted fields, so generated TypeScript marks them required.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class ReminderState(StrEnum):
    sent = "sent"
    upcoming = "upcoming"
    not_scheduled = "not_scheduled"  # its time had passed when the patient was discharged
    cancelled = "cancelled"


class TodayReminder(Schema):
    day: int
    time: str
    text: str  # in the patient's language (English if no verified translation)
    state: ReminderState
    message_id: uuid.UUID | None
    played: bool


class TodayReminders(Schema):
    recovery_day: int
    language: str
    reminders: list[TodayReminder]


class ScheduledReminder(Schema):
    id: uuid.UUID
    day: int
    time: str
    text_en: str
    due_at: datetime
    status: JobStatus
    message_id: uuid.UUID | None
