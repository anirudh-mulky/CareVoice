import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.models import DischargeStatus, ReportType


class Schema(BaseModel):
    # Responses always include defaulted fields, so generated TypeScript marks them required.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class DischargeCard(Schema):
    """The editable card the doctor sees. Every field may still be empty while drafting."""

    patient_name: str | None = Field(default=None, max_length=200)
    age: int | None = Field(default=None, ge=0, le=120)
    template_id: uuid.UUID | None = None
    template_name: str | None = None
    side: Literal["right", "left", "both"] | None = None
    language: str | None = None
    carer_phone: str | None = Field(default=None, max_length=32)
    extra_instructions: list[str] = Field(default_factory=list)


class ExtractRequest(Schema):
    transcript: str = Field(min_length=1, max_length=5000)


class PatientRef(Schema):
    id: uuid.UUID
    name: str
    age: int | None
    preferred_language: str


class ExtractResponse(Schema):
    transcript: str
    card: DischargeCard
    unclear_fields: list[str]
    matched_patient: PatientRef | None = None
    source: str
    needs_review: bool


class DischargeOut(Schema):
    id: uuid.UUID
    status: DischargeStatus
    card: DischargeCard
    unclear_fields: list[str]
    patient: PatientRef
    template_version: int
    discharged_on: date
    recovery_day: int
    approved_at: datetime | None
    created_at: datetime


class DischargeListItem(Schema):
    id: uuid.UUID
    status: DischargeStatus
    patient_name: str
    age: int | None
    language: str
    template_name: str
    discharged_on: date
    recovery_day: int
    approved_at: datetime | None
    new_reports: int = 0  # confirmed reports the doctor has not opened
    latest_report_id: uuid.UUID | None = None
    latest_report_type: ReportType | None = None


class TemplateOption(Schema):
    id: uuid.UUID
    version: int
    name: str
    condition: str


ApproveOutcome = Literal["approved", "already_approved"]


class ApproveResult(Schema):
    outcome: ApproveOutcome
    discharge: DischargeOut
