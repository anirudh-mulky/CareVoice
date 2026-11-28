"""The CareVoice data model (spec: "Data model").

Every tenant table carries hospital_id so multi-hospital tenancy needs no migration.
All ids are UUIDs, all times are UTC, and events is append-only.

The schema is shared here in core so feature modules never import each other's models.
"""

import enum
import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from app.core.db import Base

# jsonb on Postgres, JSON text on SQLite.
JsonType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


def _enum(cls: type[enum.Enum]) -> Enum:
    return Enum(cls, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])


class Role(enum.StrEnum):
    doctor = "doctor"
    nurse = "nurse"
    admin = "admin"


class DischargeStatus(enum.StrEnum):
    draft = "draft"
    sent = "sent"
    understood = "understood"
    needs_followup = "needs_followup"
    alert = "alert"
    closed = "closed"


class MessageDirection(enum.StrEnum):
    to_patient = "to_patient"
    to_doctor = "to_doctor"


class MessageKind(enum.StrEnum):
    instructions = "instructions"
    reminder = "reminder"
    teachback_q = "teachback_q"
    teachback_a = "teachback_a"
    report = "report"
    remedy = "remedy"
    doctor_reply = "doctor_reply"
    safety = "safety"  # automatic "visit the hospital today" message on a red flag


class ReportType(enum.StrEnum):
    alert = "alert"
    minor = "minor"
    general = "general"


class ReportStatus(enum.StrEnum):
    new = "new"
    seen = "seen"
    remedy_sent = "remedy_sent"
    replied = "replied"


class JobStatus(enum.StrEnum):
    pending = "pending"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"  # the care episode closed before it was due


class ActorType(enum.StrEnum):
    system = "system"
    doctor = "doctor"
    nurse = "nurse"
    patient = "patient"
    carer = "carer"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, default=uuid.uuid4)


def _hospital_fk() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow)


class Hospital(Base):
    __tablename__ = "hospitals"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(32))  # the patient's "Call hospital" button
    default_languages: Mapped[list[str]] = mapped_column(JsonType, default=list)
    created_at: Mapped[datetime] = _created_at()


class User(Base):
    """Staff only; patients are not users in Round 2."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    hospital_id: Mapped[uuid.UUID] = _hospital_fk()
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[Role] = mapped_column(_enum(Role))
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(254))
    created_at: Mapped[datetime] = _created_at()


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = _uuid_pk()
    hospital_id: Mapped[uuid.UUID] = _hospital_fk()
    name: Mapped[str] = mapped_column(String(200))
    age: Mapped[int | None] = mapped_column(Integer)  # None until the doctor says it
    sex: Mapped[str] = mapped_column(String(16))
    phone: Mapped[str | None] = mapped_column(String(32))
    preferred_language: Mapped[str] = mapped_column(String(8))
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_version: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = _created_at()


class Carer(Base):
    """Receives everything the patient receives."""

    __tablename__ = "carers"

    id: Mapped[uuid.UUID] = _uuid_pk()
    hospital_id: Mapped[uuid.UUID] = _hospital_fk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    relation: Mapped[str] = mapped_column(String(50))
    phone: Mapped[str | None] = mapped_column(String(32))
    preferred_language: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = _created_at()


class Template(Base):
    """Versioned: (id, version) is the key, and a discharge pins the version it used."""

    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    version: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    hospital_id: Mapped[uuid.UUID] = _hospital_fk()
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200))
    condition: Mapped[str] = mapped_column(String(200))
    # [{name, dose, frequency, duration_days}]
    medicines: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    dos: Mapped[list[str]] = mapped_column(JsonType, default=list)
    donts: Mapped[list[str]] = mapped_column(JsonType, default=list)
    # [{id, label_en, keywords: {lang: [...]}}]
    red_flags: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    # [{id, symptom_en, remedy_en, keywords: {lang: [...]}}]
    minor_symptoms: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    # [{day, time, message_en}]
    reminders: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    follow_up_day: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = _created_at()


class TemplateTranslation(Base):
    """Translated once per template version and language; verified by a doctor or native speaker."""

    __tablename__ = "template_translations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["template_id", "version"],
            ["templates.id", "templates.version"],
            ondelete="CASCADE",
        ),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    language: Mapped[str] = mapped_column(String(8), primary_key=True)
    hospital_id: Mapped[uuid.UUID] = _hospital_fk()
    content: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    verified_by: Mapped[str | None] = mapped_column(String(200))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Discharge(Base):
    """One per episode of care."""

    __tablename__ = "discharges"
    __table_args__ = (
        ForeignKeyConstraint(
            ["template_id", "template_version"],
            ["templates.id", "templates.version"],
        ),
        Index("ix_discharges_hospital_status", "hospital_id", "status"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    hospital_id: Mapped[uuid.UUID] = _hospital_fk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    template_id: Mapped[uuid.UUID] = mapped_column()
    template_version: Mapped[int] = mapped_column(Integer)
    side: Mapped[str | None] = mapped_column(String(16))  # right / left / both (e.g. which eye)
    extra_instructions: Mapped[list[str]] = mapped_column(JsonType, default=list)
    discharged_on: Mapped[date] = mapped_column(Date)
    status: Mapped[DischargeStatus] = mapped_column(
        _enum(DischargeStatus), default=DischargeStatus.draft
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class Message(Base):
    """The WhatsApp-style chat between patient and care team."""

    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_discharge_created", "discharge_id", "created_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    hospital_id: Mapped[uuid.UUID] = _hospital_fk()
    discharge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("discharges.id", ondelete="CASCADE"))
    direction: Mapped[MessageDirection] = mapped_column(_enum(MessageDirection))
    kind: Mapped[MessageKind] = mapped_column(_enum(MessageKind))
    text_native: Mapped[str | None] = mapped_column(Text)
    text_en: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(8))
    audio_url: Mapped[str | None] = mapped_column(String(500))
    played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class Report(Base):
    """The doctor's English report built from a patient's spoken symptom."""

    __tablename__ = "reports"
    __table_args__ = (Index("ix_reports_status_created", "status", "created_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    hospital_id: Mapped[uuid.UUID] = _hospital_fk()
    discharge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discharges.id", ondelete="CASCADE"), index=True
    )
    audio_url: Mapped[str | None] = mapped_column(String(500))
    transcript_native: Mapped[str] = mapped_column(Text)
    detected_language: Mapped[str] = mapped_column(String(8))
    stt_confidence: Mapped[float | None] = mapped_column(Float)
    translation_en: Mapped[str | None] = mapped_column(Text)
    report_json: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    matched_flag_ids: Mapped[list[str]] = mapped_column(JsonType, default=list)
    matched_minor_ids: Mapped[list[str]] = mapped_column(JsonType, default=list)
    # [{minor_id, remedy_en}] — always copied from the template, never LLM text
    suggested_remedies: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    type: Mapped[ReportType] = mapped_column(_enum(ReportType))
    status: Mapped[ReportStatus] = mapped_column(_enum(ReportStatus), default=ReportStatus.new)
    reported_by: Mapped[ActorType] = mapped_column(_enum(ActorType), default=ActorType.patient)
    confirmed_by_patient: Mapped[bool] = mapped_column(Boolean, default=False)
    # The patient said "no" to the read-back: kept for the audit, never shown to the doctor.
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class Event(Base):
    """Append-only audit timeline. Rows are never updated or deleted."""

    __tablename__ = "events"
    __table_args__ = (Index("ix_events_discharge_created", "discharge_id", "created_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    hospital_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("hospitals.id", ondelete="CASCADE"), index=True
    )
    discharge_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("discharges.id", ondelete="CASCADE")
    )
    actor_type: Mapped[ActorType] = mapped_column(_enum(ActorType), default=ActorType.system)
    actor_id: Mapped[uuid.UUID | None] = mapped_column()
    type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = _created_at()


class ScheduledJob(Base):
    """Reminders and retries."""

    __tablename__ = "scheduled_jobs"
    __table_args__ = (Index("ix_scheduled_jobs_status_due", "status", "due_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    hospital_id: Mapped[uuid.UUID] = _hospital_fk()
    discharge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("discharges.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[JobStatus] = mapped_column(_enum(JobStatus), default=JobStatus.pending)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = _created_at()


class AccessToken(Base):
    """Patient and carer links: no login, an unguessable token in the URL (spec: "API design").

    Only a SHA-256 hash is stored, so a database leak does not leak working links.
    Tokens expire after the care episode and can be revoked.
    """

    __tablename__ = "access_tokens"

    id: Mapped[uuid.UUID] = _uuid_pk()
    hospital_id: Mapped[uuid.UUID] = _hospital_fk()
    discharge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discharges.id", ondelete="CASCADE"), index=True
    )
    recipient_type: Mapped[ActorType] = mapped_column(_enum(ActorType))  # patient or carer
    recipient_id: Mapped[uuid.UUID] = mapped_column()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class AppendOnlyError(RuntimeError):
    pass


@event.listens_for(Event, "before_update")
def _block_event_update(_mapper: Mapper[Event], _conn: Any, _target: Event) -> None:
    raise AppendOnlyError("events is append-only: rows cannot be updated")


@event.listens_for(Event, "before_delete")
def _block_event_delete(_mapper: Mapper[Event], _conn: Any, _target: Event) -> None:
    raise AppendOnlyError("events is append-only: rows cannot be deleted")
