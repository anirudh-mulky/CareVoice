"""Timeline: every event for one care episode, in time order, in plain English.

Built from the append-only events table. An event type this module does not know yet is
still shown (with its raw name) and logged once, so new features never vanish from the
record.
"""

import logging
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import not_found
from app.core.events import (
    ALERT_HANDLED,
    DEMO_DAY_ADVANCED,
    DISCHARGE_APPROVED,
    DOCTOR_REPLIED,
    EPISODE_CLOSED,
    MESSAGE_PLAYED,
    MESSAGE_SENT,
    PATIENT_LANGUAGE_CHANGED,
    REMEDY_APPROVED,
    REMINDER_DUE,
    REMINDERS_SCHEDULED,
    REPORT_ALERT,
    REPORT_CONFIRMED,
    REPORT_REJECTED,
    REPORT_SEEN,
    TEACHBACK_SCORED,
    DomainEvent,
)
from app.core.models import ActorType, Discharge, Event, Message, Patient, Report, Template
from app.modules.timeline.schemas import Timeline, TimelineEntry

logger = logging.getLogger("carevoice.timeline")

# message.sent for these kinds duplicates a more specific event (remedy.approved, ...).
COVERED_KINDS = {"remedy", "doctor_reply", "reminder"}
KIND_NAMES = {
    "instructions": "care card",
    "teachback_q": "teach-back question",
    "safety": "safety message",
    "remedy": "remedy",
    "doctor_reply": "doctor's reply",
    "reminder": "reminder",
}
WHO = {
    ActorType.patient: "Patient",
    ActorType.carer: "Carer",
    ActorType.doctor: "Doctor",
    ActorType.system: "CareVoice",
}

Line = tuple[str, str | None, str, uuid.UUID | None]  # title, detail, tone, report id


class Lookup:
    """Messages and reports referenced by event payloads, loaded once each."""

    def __init__(self, session: Session, template: Template) -> None:
        self.session = session
        self.flags = {f["id"]: f["label_en"] for f in template.red_flags}
        self.minors = {m["id"]: m["symptom_en"] for m in template.minor_symptoms}

    def message(self, payload: dict[str, Any], key: str = "message_id") -> Message | None:
        value = payload.get(key)
        return self.session.get(Message, uuid.UUID(str(value))) if value else None

    def report(self, payload: dict[str, Any]) -> Report | None:
        value = payload.get("report_id")
        return self.session.get(Report, uuid.UUID(str(value))) if value else None


def _text(message: Message | None) -> str | None:
    return (message.text_en or message.text_native) if message else None


def _failed(payload: dict[str, Any]) -> str:
    bad = [d for d in payload.get("deliveries", []) if d.get("state") != "sent"]
    return f" (not delivered to {len(bad)} recipient(s))" if bad else ""


def _approved(e: Event, look: Lookup) -> Line:
    return "Discharge approved; care card sent to patient and carer", None, "neutral", None


def _sent(e: Event, look: Lookup) -> Line | None:
    kind = str(e.payload.get("kind", ""))
    if kind in COVERED_KINDS:
        return None
    name = KIND_NAMES.get(kind, kind or "message")
    tone = "danger" if kind == "safety" else "neutral"
    detail = _text(look.message(e.payload))
    return f"{name.capitalize()} sent{_failed(e.payload)}", detail, tone, None


def _played(e: Event, look: Lookup) -> Line:
    message = look.message(e.payload)
    name = KIND_NAMES.get(message.kind.value, "message") if message else "message"
    again = "" if e.payload.get("first_play", True) else " again"
    return f"{WHO.get(e.actor_type, 'Someone')} played the {name}{again}", None, "neutral", None


def _teachback(e: Event, look: Lookup) -> Line:
    p = e.payload
    named = len(p.get("mentioned_flag_ids", []))
    total = named + len(p.get("missed_flag_ids", []))
    outcome = p.get("outcome")
    ending = {
        "understood": "understood",
        "try_again": "missed signs re-explained",
        "needs_followup": "needs follow-up",
    }.get(str(outcome), str(outcome))
    who = WHO.get(e.actor_type, "Patient")
    title = (
        f"Teach-back try {p.get('try', '?')} ({who.lower()}): "
        f"named {named} of {total} warning signs, {ending}"
    )
    missed = [look.flags.get(i, i) for i in p.get("missed_flag_ids", [])]
    tone = {"understood": "good", "needs_followup": "warning"}.get(str(outcome), "neutral")
    return title, ("Missed: " + "; ".join(missed)) if missed else None, tone, None


def _confirmed(e: Event, look: Lookup) -> Line:
    report = look.report(e.payload)
    kind = str(e.payload.get("type") or (report.type.value if report else "report"))
    who = "Carer" if e.payload.get("reported_by") == "carer" else "Patient"
    summary = str((report.report_json or {}).get("summary_en", "")) if report else None
    tone = {"alert": "danger", "minor": "warning"}.get(kind, "neutral")
    return (
        f"{who} reported a symptom and confirmed the read-back ({kind})",
        summary,
        tone,
        (report.id if report else None),
    )


def _rejected(e: Event, look: Lookup) -> Line:
    title = f"{WHO.get(e.actor_type, 'Patient')} said the read-back was wrong and was asked again"
    return title, None, "neutral", None


def _seen(e: Event, look: Lookup) -> Line:
    report = look.report(e.payload)
    return "Doctor opened the report", None, "neutral", report.id if report else None


def _alert(e: Event, look: Lookup) -> Line:
    flags = [look.flags.get(i, i) for i in e.payload.get("matched_flag_ids", [])]
    report = look.report(e.payload)
    title = "Alert raised: dashboard turned red"
    return (
        title,
        ("Red flags: " + "; ".join(flags)) if flags else None,
        "danger",
        (report.id if report else None),
    )


def _remedy(e: Event, look: Lookup) -> Line:
    names = [look.minors.get(i, i) for i in e.payload.get("minor_ids", [])]
    title = f"Doctor approved a template remedy ({', '.join(names)}) and it was sent"
    return title, _text(look.message(e.payload)), "good", None


def _replied(e: Event, look: Lookup) -> Line:
    note = "" if e.payload.get("translated", True) else " (in English: no translation)"
    return f"Doctor replied{note}", _text(look.message(e.payload)), "good", None


def _handled(e: Event, look: Lookup) -> Line:
    after = str(e.payload.get("status_after", "")).replace("_", " ")
    return f"Doctor marked the alert handled (now {after})", None, "good", None


def _closed(e: Event, look: Lookup) -> Line:
    return "Care episode closed; patient and carer links stopped working", None, "neutral", None


def _scheduled(e: Event, look: Lookup) -> Line:
    n = int(e.payload.get("scheduled", 0))
    return f"{n} reminder{'s' if n != 1 else ''} scheduled from the template", None, "neutral", None


def _reminder(e: Event, look: Lookup) -> Line:
    p = e.payload
    title = f"Reminder sent (day {p.get('day', '?')}, {p.get('time', '')})"
    return title, _text(look.message(p)), "neutral", None


def _language(e: Event, look: Lookup) -> Line:
    how = "by voice" if e.payload.get("by_voice") else "on screen"
    who = WHO.get(e.actor_type, "Patient")
    title = f"{who} changed language {how}: {e.payload.get('from')} to {e.payload.get('to')}"
    return title, None, "neutral", None


def _day(e: Event, look: Lookup) -> Line:
    return (
        f"Demo: moved to recovery day {e.payload.get('recovery_day', '?')}",
        None,
        "neutral",
        None,
    )


DESCRIBE: dict[str, Callable[[Event, Lookup], Line | None]] = {
    DISCHARGE_APPROVED: _approved,
    MESSAGE_SENT: _sent,
    MESSAGE_PLAYED: _played,
    TEACHBACK_SCORED: _teachback,
    REPORT_CONFIRMED: _confirmed,
    REPORT_REJECTED: _rejected,
    REPORT_SEEN: _seen,
    REPORT_ALERT: _alert,
    REMEDY_APPROVED: _remedy,
    DOCTOR_REPLIED: _replied,
    ALERT_HANDLED: _handled,
    EPISODE_CLOSED: _closed,
    REMINDERS_SCHEDULED: _scheduled,
    REMINDER_DUE: _reminder,
    DEMO_DAY_ADVANCED: _day,
    PATIENT_LANGUAGE_CHANGED: _language,
}
_warned: set[str] = set()


def notice(event: DomainEvent, _session: Session) -> None:
    """Listens to every event: flag new event types so they get a plain-English line."""
    if event.discharge_id and event.type not in DESCRIBE and event.type not in _warned:
        _warned.add(event.type)
        logger.warning("timeline has no description for event %s yet", event.type)


def timeline(session: Session, hospital_id: uuid.UUID, discharge_id: uuid.UUID) -> Timeline:
    discharge = session.get(Discharge, discharge_id)
    if discharge is None or discharge.hospital_id != hospital_id:
        raise not_found("Discharge")
    patient = session.get(Patient, discharge.patient_id)
    template = session.get(Template, (discharge.template_id, discharge.template_version))
    assert patient is not None and template is not None
    look = Lookup(session, template)
    rows = session.scalars(
        select(Event).where(Event.discharge_id == discharge_id).order_by(Event.created_at, Event.id)
    )
    entries = []
    for event in rows:
        describe = DESCRIBE.get(event.type)
        line = (
            describe(event, look)
            if describe
            else (
                event.type.replace(".", " ").replace("_", " ").capitalize(),
                None,
                "neutral",
                None,
            )
        )
        if line is None:
            continue
        title, detail, tone, report_id = line
        entries.append(
            TimelineEntry(
                id=event.id,
                at=event.created_at,
                type=event.type,
                actor=event.actor_type,
                title=title,
                detail=detail,
                tone=tone,
                report_id=report_id,
            )
        )
    return Timeline(
        discharge_id=discharge.id,
        patient_name=patient.name,
        status=discharge.status,
        entries=entries,
    )
