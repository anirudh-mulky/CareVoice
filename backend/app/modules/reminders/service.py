"""Reminders: the template's timed messages ("Day 3, 09:00: time for your eye drops"),
scheduled when a discharge is approved and sent to the patient and carers when due.

Template times are hospital-local. A reminder whose time has already passed when the
patient is discharged is not scheduled (a 08:00 reminder is not sent at 14:00). The text
comes from the template's verified translation; English if there is none.
"""

import asyncio
import logging
import uuid
from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.channels.recipients import send_to_family
from app.channels.registry import ChannelRegistry
from app.core.config import Settings
from app.core.db import Database
from app.core.errors import not_found
from app.core.events import (
    MESSAGE_SENT,
    REMINDER_DUE,
    REMINDERS_SCHEDULED,
    DomainEvent,
    EventBus,
)
from app.core.models import (
    Discharge,
    DischargeStatus,
    JobStatus,
    Message,
    MessageDirection,
    MessageKind,
    Patient,
    ScheduledJob,
    Template,
    TemplateTranslation,
)
from app.core.patient_access import PatientAccess
from app.modules.reminders.schemas import (
    ReminderState,
    ScheduledReminder,
    TodayReminder,
    TodayReminders,
)

logger = logging.getLogger("carevoice.reminders")
KIND = "reminder"
MAX_ATTEMPTS = 3
OPEN = (
    DischargeStatus.sent,
    DischargeStatus.understood,
    DischargeStatus.needs_followup,
    DischargeStatus.alert,
)


def hospital_tz(settings: Settings) -> timezone:
    return timezone(timedelta(minutes=settings.hospital_utc_offset_minutes))


def due_at(discharged_on: date, day: int, at: str, tz: timezone) -> datetime:
    """Day 1 is the day of discharge; `at` is "HH:MM" hospital time."""
    hour, minute = (int(x) for x in at.split(":"))
    local = datetime.combine(discharged_on + timedelta(days=day - 1), time(hour, minute), tz)
    return local.astimezone(UTC)


def end_of_local_day(now: datetime, tz: timezone) -> datetime:
    local = now.astimezone(tz)
    return datetime.combine(local.date(), time.max, tz).astimezone(UTC)


def recovery_day(discharge: Discharge) -> int:
    return max(1, (datetime.now(UTC).date() - discharge.discharged_on).days + 1)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class Episode:
    def __init__(self, session: Session, discharge_id: uuid.UUID) -> None:
        discharge = session.get(Discharge, discharge_id)
        if discharge is None:
            raise not_found("Discharge")
        patient = session.get(Patient, discharge.patient_id)
        template = session.get(Template, (discharge.template_id, discharge.template_version))
        assert patient is not None and template is not None
        self.discharge, self.patient, self.template = discharge, patient, template
        wanted = patient.preferred_language
        self.translation = session.get(TemplateTranslation, (template.id, template.version, wanted))
        self.lang = wanted if (self.translation or wanted == "en") else "en"

    def text(self, index: int) -> tuple[str, str]:
        """(patient's language, English) for the template's reminder at `index`."""
        reminder = self.template.reminders[index]
        english = str(reminder["message_en"])
        native_list = (self.translation.content if self.translation else {}).get("reminders", [])
        if len(native_list) == len(self.template.reminders):
            native = native_list[index].get("message")
        else:  # fall back to the same day's reminder
            native = next(
                (r.get("message") for r in native_list if r.get("day") == reminder["day"]), None
            )
        return (str(native) if native and self.lang != "en" else english), english


def _jobs(session: Session, discharge_id: uuid.UUID) -> list[ScheduledJob]:
    return list(
        session.scalars(
            select(ScheduledJob)
            .where(ScheduledJob.discharge_id == discharge_id, ScheduledJob.kind == KIND)
            .order_by(ScheduledJob.due_at)
        )
    )


# --- Scheduling -----------------------------------------------------------------------------


def schedule(
    session: Session,
    bus: EventBus,
    settings: Settings,
    discharge_id: uuid.UUID,
    now: datetime | None = None,
) -> int:
    """Create a job for each of the template's reminders that is still ahead. Idempotent."""
    episode = Episode(session, discharge_id)
    discharge = episode.discharge
    if discharge.status not in OPEN or _jobs(session, discharge.id):
        return 0
    now = now or datetime.now(UTC)
    tz = hospital_tz(settings)
    created, passed = 0, 0
    for index, reminder in enumerate(episode.template.reminders):
        due = due_at(discharge.discharged_on, int(reminder["day"]), str(reminder["time"]), tz)
        if due <= now:
            passed += 1
            continue
        session.add(
            ScheduledJob(
                hospital_id=discharge.hospital_id,
                discharge_id=discharge.id,
                kind=KIND,
                payload={"day": reminder["day"], "time": reminder["time"], "index": index},
                due_at=due,
            )
        )
        created += 1
    session.flush()
    bus.publish(
        session,
        DomainEvent(
            type=REMINDERS_SCHEDULED,
            hospital_id=discharge.hospital_id,
            discharge_id=discharge.id,
            payload={"scheduled": created, "already_passed": passed},
        ),
    )
    return created


def schedule_missing(session: Session, bus: EventBus, settings: Settings) -> int:
    """Schedule reminders for open episodes that have none (e.g. freshly seeded demo data)."""
    with_jobs = select(ScheduledJob.discharge_id).where(ScheduledJob.kind == KIND)
    ids = session.scalars(
        select(Discharge.id).where(Discharge.status.in_(OPEN), Discharge.id.not_in(with_jobs))
    ).all()
    return sum(schedule(session, bus, settings, i) for i in ids)


def cancel(session: Session, discharge_id: uuid.UUID) -> int:
    jobs = [j for j in _jobs(session, discharge_id) if j.status is JobStatus.pending]
    for job in jobs:
        job.status = JobStatus.cancelled
    session.flush()
    return len(jobs)


# --- Sending --------------------------------------------------------------------------------


async def _send(
    session: Session, bus: EventBus, channels: ChannelRegistry, job: ScheduledJob
) -> None:
    episode = Episode(session, job.discharge_id)
    discharge = episode.discharge
    if discharge.status not in OPEN:
        job.status = JobStatus.cancelled
        return
    index = int(job.payload.get("index", 0))
    native, english = episode.text(index)
    message = Message(
        hospital_id=discharge.hospital_id,
        discharge_id=discharge.id,
        direction=MessageDirection.to_patient,
        kind=MessageKind.reminder,
        text_native=native,
        text_en=english,
        language=episode.lang,
    )
    session.add(message)
    session.flush()
    deliveries = await send_to_family(session, channels, discharge, message)
    job.status = JobStatus.done
    job.attempts += 1
    job.payload = {**job.payload, "message_id": str(message.id)}
    session.flush()
    bus.publish(
        session,
        DomainEvent(
            type=MESSAGE_SENT,
            hospital_id=discharge.hospital_id,
            discharge_id=discharge.id,
            payload={
                "message_id": str(message.id),
                "kind": MessageKind.reminder.value,
                "language": episode.lang,
                "deliveries": deliveries,
            },
        ),
    )
    bus.publish(
        session,
        DomainEvent(
            type=REMINDER_DUE,
            hospital_id=discharge.hospital_id,
            discharge_id=discharge.id,
            payload={
                "job_id": str(job.id),
                "day": job.payload.get("day"),
                "time": job.payload.get("time"),
                "message_id": str(message.id),
            },
        ),
    )


async def fire_due(
    session: Session,
    bus: EventBus,
    channels: ChannelRegistry,
    until: datetime,
    discharge_id: uuid.UUID | None = None,
) -> int:
    """Send every pending reminder due by `until`. Returns how many were sent."""
    query = select(ScheduledJob).where(
        ScheduledJob.kind == KIND,
        ScheduledJob.status == JobStatus.pending,
        ScheduledJob.due_at <= until,
    )
    if discharge_id is not None:
        query = query.where(ScheduledJob.discharge_id == discharge_id)
    sent = 0
    for job in session.scalars(query.order_by(ScheduledJob.due_at)).all():
        try:
            await _send(session, bus, channels, job)
        except Exception:  # noqa: BLE001 - one bad reminder never blocks the rest
            logger.exception("reminder %s failed", job.id)
            job.attempts += 1
            if job.attempts >= MAX_ATTEMPTS:
                job.status = JobStatus.failed
            continue
        sent += job.status is JobStatus.done
    session.flush()
    return sent


async def advance_day(
    session: Session,
    bus: EventBus,
    channels: ChannelRegistry,
    settings: Settings,
    discharge_id: uuid.UUID,
) -> int:
    """Demo "Simulate next day": bring this episode's reminders a day closer, then send
    everything due by the end of today (the new recovery day), whatever the clock says."""
    for job in _jobs(session, discharge_id):
        if job.status is JobStatus.pending:
            job.due_at = _aware(job.due_at) - timedelta(days=1)
    session.flush()
    until = end_of_local_day(datetime.now(UTC), hospital_tz(settings))
    return await fire_due(session, bus, channels, until, discharge_id)


async def tick_forever(
    db: Database, bus: EventBus, channels: ChannelRegistry, settings: Settings
) -> None:
    """Background loop: send due reminders every `reminder_tick_seconds`."""
    while True:
        await asyncio.sleep(settings.reminder_tick_seconds)
        try:
            with db.session() as session:
                await fire_due(session, bus, channels, datetime.now(UTC))
        except Exception:  # noqa: BLE001 - keep ticking
            logger.exception("reminder tick failed")


# --- Reads ----------------------------------------------------------------------------------


def today(session: Session, access: PatientAccess) -> TodayReminders:
    """Today's reminders for the patient home, in their language."""
    episode = Episode(session, access.discharge_id)
    day = recovery_day(episode.discharge)
    jobs = {int(j.payload.get("index", -1)): j for j in _jobs(session, episode.discharge.id)}
    out: list[TodayReminder] = []
    for index, reminder in enumerate(episode.template.reminders):
        if int(reminder["day"]) != day:
            continue
        native, _ = episode.text(index)
        job = jobs.get(index)
        message_id = job.payload.get("message_id") if job else None
        message = session.get(Message, uuid.UUID(message_id)) if message_id else None
        state = (
            ReminderState.not_scheduled
            if job is None
            else ReminderState.sent
            if job.status is JobStatus.done
            else ReminderState.cancelled
            if job.status is JobStatus.cancelled
            else ReminderState.upcoming
        )
        out.append(
            TodayReminder(
                day=day,
                time=str(reminder["time"]),
                text=native,
                state=state,
                message_id=message.id if message else None,
                played=bool(message and message.played_at),
            )
        )
    return TodayReminders(recovery_day=day, language=episode.lang, reminders=out)


def scheduled(
    session: Session, hospital_id: uuid.UUID, discharge_id: uuid.UUID
) -> list[ScheduledReminder]:
    """Every reminder job for one episode, for the doctor's patient page."""
    episode = Episode(session, discharge_id)
    if episode.discharge.hospital_id != hospital_id:
        raise not_found("Discharge")
    out = []
    for job in _jobs(session, discharge_id):
        payload: dict[str, Any] = job.payload
        index = int(payload.get("index", 0))
        _, english = episode.text(index)
        message_id = payload.get("message_id")
        out.append(
            ScheduledReminder(
                id=job.id,
                day=int(payload.get("day", 0)),
                time=str(payload.get("time", "")),
                text_en=english,
                due_at=_aware(job.due_at),
                status=job.status,
                message_id=uuid.UUID(message_id) if message_id else None,
            )
        )
    return out
