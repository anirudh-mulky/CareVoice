"""Outcomes: what happens after a patient confirms a report.

- Alert (red flag, low confidence or hard-to-hear speech): the discharge turns red on the
  dashboard and the patient gets an automatic safety message ("come to the hospital
  today"). Safety messages are the only thing sent without the doctor.
- Minor: the doctor approves one or more of the template's own remedies; the patient gets
  the template's verified translation. Free text is never accepted as a remedy, and
  remedies are never sent for alerts.
- General (or any report): the doctor replies by text or voice, translated.
- The doctor marks an alert handled, and can close the care episode (links stop working).
"""

import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import yaml
from sqlalchemy import CursorResult, select, update
from sqlalchemy.orm import Session

from app.channels.recipients import send_to_family
from app.channels.registry import ChannelRegistry
from app.core.errors import AppError, not_found
from app.core.events import (
    ALERT_HANDLED,
    DOCTOR_REPLIED,
    EPISODE_CLOSED,
    MESSAGE_SENT,
    REMEDY_APPROVED,
    REPORT_ALERT,
    DomainEvent,
    EventBus,
)
from app.core.models import (
    ActorType,
    Carer,
    Discharge,
    DischargeStatus,
    Event,
    Message,
    MessageDirection,
    MessageKind,
    Patient,
    Report,
    ReportStatus,
    ReportType,
    Template,
    TemplateTranslation,
)
from app.core.patient_access import revoke_tokens
from app.modules.outcomes.schemas import (
    ActionResult,
    QuickReply,
    RemedyOption,
    ReplyPreview,
    ReportActions,
    SentMessage,
)
from app.providers.registry import ProviderRegistry

HERE = Path(__file__).parent
PATIENT_KINDS = (MessageKind.safety, MessageKind.remedy, MessageKind.doctor_reply)
# Statuses an alert may interrupt (and that "handled" can return to).
OPEN = (DischargeStatus.sent, DischargeStatus.understood, DischargeStatus.needs_followup)


@lru_cache
def phrases() -> dict[str, dict[str, str]]:
    data: dict[str, dict[str, str]] = yaml.safe_load((HERE / "phrases.yaml").read_text("utf-8"))
    return data


def phrase(lang: str, key: str) -> str:
    table = phrases().get(lang) or phrases()["en"]
    return str(table.get(key) or phrases()["en"][key])


@lru_cache
def quick_replies() -> list[dict[str, str]]:
    data: list[dict[str, str]] = yaml.safe_load((HERE / "quick_replies.yaml").read_text("utf-8"))
    return data


def install_quick_replies(providers: ProviderRegistry) -> None:
    """Teach the demo translator the quick replies, so they arrive translated."""
    for reply in quick_replies():
        for lang, text in reply.items():
            if lang != "id":
                providers.demo_translator.add(f"quick_reply:{reply['id']}", lang, text)


# --- Shared helpers -------------------------------------------------------------------------


class Episode:
    def __init__(self, session: Session, discharge_id: uuid.UUID) -> None:
        discharge = session.get(Discharge, discharge_id)
        if discharge is None:
            raise not_found("Discharge")
        patient = session.get(Patient, discharge.patient_id)
        template = session.get(Template, (discharge.template_id, discharge.template_version))
        assert patient is not None and template is not None
        self.discharge, self.patient, self.template = discharge, patient, template
        self.lang = patient.preferred_language
        self.translation = session.get(
            TemplateTranslation, (template.id, template.version, self.lang)
        )
        self.carers = list(session.scalars(select(Carer).where(Carer.patient_id == patient.id)))

    def remedy_native(self, minor_id: str) -> tuple[str, bool]:
        english = {m["id"]: m["remedy_en"] for m in self.template.minor_symptoms}[minor_id]
        if self.lang == "en":
            return english, True
        native = {
            m["id"]: m.get("remedy")
            for m in (self.translation.content if self.translation else {}).get(
                "minor_symptoms", []
            )
        }.get(minor_id)
        return (native, True) if native else (english, False)


def _sent(message: Message) -> SentMessage:
    return SentMessage(
        id=message.id,
        kind=message.kind,
        text_native=message.text_native or "",
        text_en=message.text_en,
        language=message.language,
        created_at=message.created_at,
    )


async def _post_to_patient(
    session: Session,
    bus: EventBus,
    channels: ChannelRegistry,
    episode: Episode,
    kind: MessageKind,
    native: str,
    english: str,
    actor: tuple[ActorType, uuid.UUID | None] = (ActorType.system, None),
) -> Message:
    message = Message(
        hospital_id=episode.discharge.hospital_id,
        discharge_id=episode.discharge.id,
        direction=MessageDirection.to_patient,
        kind=kind,
        text_native=native,
        text_en=english,
        language=episode.lang,
    )
    session.add(message)
    session.flush()
    deliveries = await send_to_family(session, channels, episode.discharge, message)
    bus.publish(
        session,
        DomainEvent(
            type=MESSAGE_SENT,
            hospital_id=episode.discharge.hospital_id,
            discharge_id=episode.discharge.id,
            actor_type=actor[0],
            actor_id=actor[1],
            payload={
                "message_id": str(message.id),
                "kind": kind.value,
                "language": episode.lang,
                "deliveries": deliveries,
            },
        ),
    )
    return message


# --- On report.confirmed: alerts ------------------------------------------------------------


async def on_report_confirmed(
    session: Session, bus: EventBus, channels: ChannelRegistry, report_id: uuid.UUID
) -> Message | None:
    """Alerts act at once (dashboard + safety message); minor and general wait for the doctor."""
    report = session.get(Report, report_id)
    if report is None or report.type is not ReportType.alert:
        return None
    episode = Episode(session, report.discharge_id)
    discharge = episode.discharge
    if discharge.status in (DischargeStatus.draft, DischargeStatus.closed):
        return None
    before = discharge.status
    discharge.status = DischargeStatus.alert
    session.flush()
    message = await _post_to_patient(
        session,
        bus,
        channels,
        episode,
        MessageKind.safety,
        phrase(episode.lang, "safety"),
        phrase("en", "safety"),
    )
    bus.publish(
        session,
        DomainEvent(
            type=REPORT_ALERT,
            hospital_id=discharge.hospital_id,
            discharge_id=discharge.id,
            payload={
                "report_id": str(report.id),
                "status_before": before.value,
                "safety_message_id": str(message.id),
                "matched_flag_ids": list(report.matched_flag_ids),
                "reasons": list((report.report_json or {}).get("reasons", [])),
            },
        ),
    )
    return message


# --- Doctor: what can be done with this report ----------------------------------------------


def _report(session: Session, hospital_id: uuid.UUID, report_id: uuid.UUID) -> Report:
    report = session.get(Report, report_id)
    if report is None or report.hospital_id != hospital_id or not report.confirmed_by_patient:
        raise not_found("Report")
    return report


def actions(session: Session, hospital_id: uuid.UUID, report_id: uuid.UUID) -> ReportActions:
    report = _report(session, hospital_id, report_id)
    episode = Episode(session, report.discharge_id)
    suggested = {r.get("minor_id") for r in report.suggested_remedies} | set(
        report.matched_minor_ids
    )
    options = []
    for m in episode.template.minor_symptoms:
        native, translated = episode.remedy_native(m["id"])
        options.append(
            RemedyOption(
                minor_id=m["id"],
                symptom_en=m["symptom_en"],
                remedy_en=m["remedy_en"],
                remedy_native=native,
                translated=translated,
                suggested=m["id"] in suggested,
            )
        )
    sent = session.scalars(
        select(Message)
        .where(
            Message.discharge_id == report.discharge_id,
            Message.kind.in_(PATIENT_KINDS),
            Message.created_at >= report.created_at,
        )
        .order_by(Message.created_at)
    )
    status = episode.discharge.status
    return ReportActions(
        report_id=report.id,
        discharge_id=report.discharge_id,
        report_type=report.type,
        report_status=report.status,
        discharge_status=status,
        language=episode.lang,
        can_send_remedy=report.type is not ReportType.alert
        and report.status in (ReportStatus.new, ReportStatus.seen)
        and status is not DischargeStatus.closed,
        can_handle_alert=status is DischargeStatus.alert,
        can_close=status is not DischargeStatus.closed,
        remedy_options=options,
        quick_replies=[QuickReply(id=q["id"], text_en=q["en"]) for q in quick_replies()],
        sent=[_sent(m) for m in sent],
    )


# --- Doctor: approve a template remedy ------------------------------------------------------


async def approve_remedy(
    session: Session,
    bus: EventBus,
    channels: ChannelRegistry,
    hospital_id: uuid.UUID,
    doctor_id: uuid.UUID,
    report_id: uuid.UUID,
    minor_ids: list[str],
) -> ActionResult:
    report = _report(session, hospital_id, report_id)
    episode = Episode(session, report.discharge_id)
    if report.type is ReportType.alert:
        raise AppError(
            409, "alert_needs_call", "This is an alert: call the patient instead of a remedy."
        )
    if episode.discharge.status is DischargeStatus.closed:
        raise AppError(409, "episode_closed", "This care episode is closed.")
    known = [m["id"] for m in episode.template.minor_symptoms]
    unknown = [i for i in minor_ids if i not in known]
    if unknown:
        # Remedies come only from the doctor's template.
        raise AppError(422, "not_in_template", "Pick remedies from the template.", {"ids": unknown})
    if report.status is ReportStatus.remedy_sent:
        return ActionResult(
            outcome="already_sent",
            discharge_status=episode.discharge.status,
            report_status=report.status,
        )

    # Atomic claim: a double tap sends the remedy once.
    claimed = cast(
        CursorResult[Any],
        session.execute(
            update(Report)
            .where(Report.id == report.id, Report.status.in_([ReportStatus.new, ReportStatus.seen]))
            .values(status=ReportStatus.remedy_sent)
            .execution_options(synchronize_session=False)
        ),
    ).rowcount
    session.refresh(report)
    if not claimed:
        return ActionResult(
            outcome="already_sent",
            discharge_status=episode.discharge.status,
            report_status=report.status,
        )

    chosen = [i for i in known if i in minor_ids]  # template order, no duplicates
    english_by_id = {m["id"]: m["remedy_en"] for m in episode.template.minor_symptoms}
    natives = [episode.remedy_native(i) for i in chosen]
    native = " ".join([phrase(episode.lang, "remedy_intro"), *(n for n, _ in natives)])
    english = " ".join([phrase("en", "remedy_intro"), *(english_by_id[i] for i in chosen)])
    message = await _post_to_patient(
        session,
        bus,
        channels,
        episode,
        MessageKind.remedy,
        native,
        english,
        (ActorType.doctor, doctor_id),
    )
    bus.publish(
        session,
        DomainEvent(
            type=REMEDY_APPROVED,
            hospital_id=report.hospital_id,
            discharge_id=report.discharge_id,
            actor_type=ActorType.doctor,
            actor_id=doctor_id,
            payload={
                "report_id": str(report.id),
                "minor_ids": chosen,
                "message_id": str(message.id),
                "translated": all(t for _, t in natives),
            },
        ),
    )
    return ActionResult(
        outcome="sent",
        message=_sent(message),
        discharge_status=episode.discharge.status,
        report_status=report.status,
    )


# --- Doctor: reply by text or voice ---------------------------------------------------------


async def preview_reply(
    session: Session,
    providers: ProviderRegistry,
    hospital_id: uuid.UUID,
    report_id: uuid.UUID,
    text: str,
) -> ReplyPreview:
    report = _report(session, hospital_id, report_id)
    lang = Episode(session, report.discharge_id).lang
    native = await providers.translator.translate(text, "en", lang)
    translated = lang == "en" or (bool(native) and native != text)
    return ReplyPreview(
        language=lang, text_native=native if translated else text, translated=translated
    )


async def reply(
    session: Session,
    bus: EventBus,
    providers: ProviderRegistry,
    channels: ChannelRegistry,
    hospital_id: uuid.UUID,
    doctor_id: uuid.UUID,
    report_id: uuid.UUID,
    text: str,
    idempotency_key: str | None = None,
) -> ActionResult:
    report = _report(session, hospital_id, report_id)
    episode = Episode(session, report.discharge_id)
    if episode.discharge.status is DischargeStatus.closed:
        raise AppError(409, "episode_closed", "This care episode is closed.")
    if idempotency_key:
        earlier = session.scalars(
            select(Event).where(
                Event.discharge_id == report.discharge_id, Event.type == DOCTOR_REPLIED
            )
        ).all()
        for event in earlier:
            if event.payload.get("idempotency_key") == idempotency_key:
                message = session.get(Message, uuid.UUID(event.payload["message_id"]))
                return ActionResult(
                    outcome="already_sent",
                    message=_sent(message) if message else None,
                    discharge_status=episode.discharge.status,
                    report_status=report.status,
                )

    preview = await preview_reply(session, providers, hospital_id, report_id, text)
    intro = phrase(episode.lang if preview.translated else "en", "reply_intro")
    native = f"{intro} {preview.text_native}"
    message = await _post_to_patient(
        session,
        bus,
        channels,
        episode,
        MessageKind.doctor_reply,
        native,
        f"{phrase('en', 'reply_intro')} {text}",
        (ActorType.doctor, doctor_id),
    )
    if report.status is not ReportStatus.remedy_sent:
        report.status = ReportStatus.replied
    session.flush()
    bus.publish(
        session,
        DomainEvent(
            type=DOCTOR_REPLIED,
            hospital_id=report.hospital_id,
            discharge_id=report.discharge_id,
            actor_type=ActorType.doctor,
            actor_id=doctor_id,
            payload={
                "report_id": str(report.id),
                "message_id": str(message.id),
                "translated": preview.translated,
                "idempotency_key": idempotency_key,
            },
        ),
    )
    return ActionResult(
        outcome="sent",
        message=_sent(message),
        discharge_status=episode.discharge.status,
        report_status=report.status,
    )


# --- Doctor: alert handled, close the episode -----------------------------------------------


def _discharge(session: Session, hospital_id: uuid.UUID, discharge_id: uuid.UUID) -> Discharge:
    discharge = session.get(Discharge, discharge_id)
    if discharge is None or discharge.hospital_id != hospital_id:
        raise not_found("Discharge")
    return discharge


def handle_alert(
    session: Session,
    bus: EventBus,
    hospital_id: uuid.UUID,
    doctor_id: uuid.UUID,
    discharge_id: uuid.UUID,
) -> ActionResult:
    """The doctor has dealt with the alert: return to where the episode was before it."""
    discharge = _discharge(session, hospital_id, discharge_id)
    if discharge.status is not DischargeStatus.alert:
        raise AppError(409, "not_alert", "This patient has no open alert.")
    last_alert = session.scalars(
        select(Event)
        .where(Event.discharge_id == discharge.id, Event.type == REPORT_ALERT)
        .order_by(Event.created_at.desc())
    ).first()
    before = (last_alert.payload.get("status_before") if last_alert else None) or "sent"
    restored = DischargeStatus(before)
    discharge.status = restored if restored in OPEN else DischargeStatus.sent
    seen = session.execute(
        update(Report)
        .where(
            Report.discharge_id == discharge.id,
            Report.type == ReportType.alert,
            Report.status == ReportStatus.new,
            Report.confirmed_by_patient.is_(True),
        )
        .values(status=ReportStatus.seen)
        .execution_options(synchronize_session=False)
    )
    session.flush()
    bus.publish(
        session,
        DomainEvent(
            type=ALERT_HANDLED,
            hospital_id=discharge.hospital_id,
            discharge_id=discharge.id,
            actor_type=ActorType.doctor,
            actor_id=doctor_id,
            payload={
                "status_after": discharge.status.value,
                "reports_marked_seen": int(getattr(seen, "rowcount", 0) or 0),
            },
        ),
    )
    return ActionResult(outcome="handled", discharge_status=discharge.status)


def close_episode(
    session: Session,
    bus: EventBus,
    hospital_id: uuid.UUID,
    doctor_id: uuid.UUID,
    discharge_id: uuid.UUID,
) -> ActionResult:
    """End the care episode: no more reports, and the patient's links stop working."""
    discharge = _discharge(session, hospital_id, discharge_id)
    if discharge.status is DischargeStatus.draft:
        raise AppError(409, "not_sent", "A draft cannot be closed; it was never sent.")
    if discharge.status is DischargeStatus.closed:
        return ActionResult(outcome="closed", discharge_status=discharge.status)
    before = discharge.status
    discharge.status = DischargeStatus.closed
    revoked = revoke_tokens(session, discharge.id)
    session.flush()
    bus.publish(
        session,
        DomainEvent(
            type=EPISODE_CLOSED,
            hospital_id=discharge.hospital_id,
            discharge_id=discharge.id,
            actor_type=ActorType.doctor,
            actor_id=doctor_id,
            payload={
                "status_before": before.value,
                "links_revoked": revoked,
                "closed_at": datetime.now().astimezone().isoformat(),
            },
        ),
    )
    return ActionResult(outcome="closed", discharge_status=discharge.status)
