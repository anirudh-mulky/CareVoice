"""Spoken symptom reports: the patient speaks, the app reads back what it understood in
their language, and only a "yes" sends the English report to the doctor.

The type (alert / minor / general) is set by the decision rules in code. Remedies are
always copied from the doctor's template by id. Acting on the type (alerts, remedies,
replies) is the outcomes module's job: it listens to report.confirmed.
"""

import uuid
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.registry import run_task
from app.ai.tasks.analyse_symptom.schema import AnalyseSymptomInput, Symptom
from app.ai.tasks.common import FlagSpec, MinorSpec
from app.core.config import Settings
from app.core.errors import AppError, not_found
from app.core.events import (
    REPORT_CONFIRMED,
    REPORT_REJECTED,
    REPORT_SEEN,
    DomainEvent,
    EventBus,
)
from app.core.models import (
    ActorType,
    Discharge,
    DischargeStatus,
    Message,
    MessageDirection,
    MessageKind,
    Patient,
    Report,
    ReportStatus,
    ReportType,
    Template,
)
from app.core.patient_access import PatientAccess
from app.modules.reports.schemas import (
    ConfirmIn,
    ConfirmOut,
    ConfirmOutcome,
    FlagOut,
    MedicineOut,
    MinorOut,
    ReadBack,
    RemedyOut,
    ReportDetail,
    ReportIn,
    ReportListItem,
    SymptomOut,
)
from app.providers.registry import ProviderRegistry
from app.rules.decisions import decide
from app.rules.language import detect_script
from app.rules.lexicon import get_lexicon
from app.rules.yes_no import yes_or_no

PHRASES_FILE = Path(__file__).with_name("phrases.yaml")
CLOSED = (DischargeStatus.draft, DischargeStatus.closed)
AUDIO_TYPES = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
}
MEDIA_TYPES = {ext: mime for mime, ext in AUDIO_TYPES.items()}
# Doctor's list: alerts first, then unseen, then newest.
TYPE_ORDER = {ReportType.alert: 0, ReportType.minor: 1, ReportType.general: 2}


@lru_cache
def phrases() -> dict[str, dict[str, str]]:
    data: dict[str, dict[str, str]] = yaml.safe_load(PHRASES_FILE.read_text("utf-8"))
    return data


def phrase(lang: str, key: str) -> str:
    table = phrases().get(lang.split("-")[0]) or phrases()["en"]
    return str(table.get(key) or phrases()["en"][key])


def recovery_day(discharge: Discharge, on: datetime | None = None) -> int:
    day = (on or datetime.now(UTC)).date()
    return max(1, (day - discharge.discharged_on).days + 1)


def _english_medicine(m: dict[str, Any]) -> str:
    parts = [m.get("dose"), m.get("frequency")]
    if m.get("duration_days"):
        parts.append(f"{m['duration_days']} days")
    return ", ".join(str(p) for p in parts if p)


def _episode(session: Session, discharge_id: uuid.UUID) -> tuple[Discharge, Patient, Template]:
    discharge = session.get(Discharge, discharge_id)
    if discharge is None:
        raise not_found("Discharge")
    patient = session.get(Patient, discharge.patient_id)
    template = session.get(Template, (discharge.template_id, discharge.template_version))
    assert patient is not None and template is not None
    return discharge, patient, template


# --- Patient: speak, read back, confirm ---------------------------------------------------


async def create_report(
    session: Session,
    bus: EventBus,
    providers: ProviderRegistry,
    settings: Settings,
    access: PatientAccess,
    body: ReportIn,
) -> ReadBack:
    """Analyse what the patient said and return the read-back. Nothing reaches the doctor."""
    discharge, patient, template = _episode(session, access.discharge_id)
    if discharge.status in CLOSED:
        raise AppError(409, "episode_closed", "This care episode is closed. Call the hospital.")
    lang = body.language or patient.preferred_language
    day = recovery_day(discharge)
    lex = get_lexicon()

    suggested: str | None = None
    translation_en: str | None
    if body.icons:
        # Tapped icons: the words come from the lexicon, in the patient's language.
        pack = lex.pack(lang)
        joiner = f" {pack.text('joiner', 'and')} "
        transcript = joiner.join(lex.concepts[i].label(pack.code) for i in body.icons)
        translation_en = ", ".join(lex.concepts[i].label("en") for i in body.icons)
        if pack.code == "en":
            translation_en = None
    else:
        transcript = body.transcript
        # Spoke another language than their setting (e.g. Hindi script for a Kannada
        # patient)? Read back in what they spoke, and offer to switch.
        detected = detect_script(transcript)
        if detected and detected in lex.languages and detected != lang.split("-")[0]:
            lang = suggested = detected
        translated = await providers.translator.translate(transcript, lang, "en")
        translation_en = translated if translated and translated != transcript else None
    minors = [MinorSpec.model_validate(m) for m in template.minor_symptoms]
    result = await run_task(
        providers,
        "analyse_symptom",
        AnalyseSymptomInput(
            transcript_native=transcript,
            transcript_en=translation_en,
            language=lang,
            red_flags=[FlagSpec.model_validate(f) for f in template.red_flags],
            minor_symptoms=minors,
            recovery_day=day,
            medicines=[m["name"] for m in template.medicines],
        ),
    )
    symptom: Symptom = result.output
    decision = decide(symptom, minors, body.stt_confidence, settings.stt_confidence_alert_threshold)
    report = Report(
        hospital_id=discharge.hospital_id,
        discharge_id=discharge.id,
        transcript_native=transcript,
        detected_language=lang,
        stt_confidence=body.stt_confidence,
        translation_en=translation_en,
        report_json=symptom.model_dump(exclude={"suggested_remedies"})
        | {
            "recovery_day": day,
            "reasons": decision.reasons,
            "source": result.source.value,
            "needs_review": result.needs_review,
            "input": "icons" if body.icons else "speech",
            "icons": body.icons,
        },
        matched_flag_ids=symptom.matched_flag_ids,
        matched_minor_ids=symptom.matched_minor_ids,
        # Copied from the template by the decision rules; the analyser's text is ignored.
        suggested_remedies=[r.model_dump() for r in decision.remedies],
        type=ReportType(decision.type.value),
        status=ReportStatus.new,
        reported_by=access.recipient_type,
        confirmed_by_patient=False,
    )
    session.add(report)
    session.flush()
    return ReadBack(
        report_id=report.id,
        language=lang,
        read_back=symptom.read_back_native,
        suggested_language=suggested,
    )


def _own_report(session: Session, access: PatientAccess, report_id: uuid.UUID) -> Report:
    report = session.get(Report, report_id)
    if report is None or report.discharge_id != access.discharge_id:
        raise not_found("Report")
    return report


def confirm(
    session: Session, bus: EventBus, access: PatientAccess, report_id: uuid.UUID, body: ConfirmIn
) -> ConfirmOut:
    """Yes sends the English report to the doctor; no asks the patient to say it again."""
    report = _own_report(session, access, report_id)
    lang = report.detected_language

    def out(outcome: ConfirmOutcome, key: str) -> ConfirmOut:
        return ConfirmOut(report_id=report.id, outcome=outcome, message=phrase(lang, key))

    if report.confirmed_by_patient:  # a double tap returns the first result
        return out(ConfirmOutcome.sent, "sent")
    if report.rejected_at is not None:
        raise AppError(409, "report_rejected", "This report was not confirmed. Say it again.")

    answer = body.answer if body.answer is not None else yes_or_no(body.transcript or "", lang)
    if answer is None:
        return out(ConfirmOutcome.unclear, "unclear")

    if not answer:
        report.rejected_at = datetime.now(UTC)
        session.flush()
        bus.publish(
            session,
            DomainEvent(
                type=REPORT_REJECTED,
                hospital_id=report.hospital_id,
                discharge_id=report.discharge_id,
                actor_type=access.recipient_type,
                actor_id=access.recipient_id,
                payload={"report_id": str(report.id)},
            ),
        )
        return out(ConfirmOutcome.say_again, "say_again")

    report.confirmed_by_patient = True
    summary = str(report.report_json.get("summary_en") or "")
    message = Message(
        hospital_id=report.hospital_id,
        discharge_id=report.discharge_id,
        direction=MessageDirection.to_doctor,
        kind=MessageKind.report,
        text_native=report.transcript_native,
        text_en=report.translation_en or summary,
        language=lang,
        audio_url=report.audio_url,
    )
    session.add(message)
    session.flush()
    report.report_json = {**report.report_json, "message_id": str(message.id)}
    session.flush()
    bus.publish(
        session,
        DomainEvent(
            type=REPORT_CONFIRMED,
            hospital_id=report.hospital_id,
            discharge_id=report.discharge_id,
            actor_type=access.recipient_type,
            actor_id=access.recipient_id,
            payload={
                "report_id": str(report.id),
                "message_id": str(message.id),
                "type": report.type.value,
                "matched_flag_ids": list(report.matched_flag_ids),
                "matched_minor_ids": list(report.matched_minor_ids),
                "reasons": list(report.report_json.get("reasons", [])),
                "reported_by": report.reported_by.value,
                "language": lang,
                "stt_confidence": report.stt_confidence,
            },
        ),
    )
    return out(ConfirmOutcome.sent, "sent")


def save_audio(
    session: Session,
    settings: Settings,
    access: PatientAccess,
    report_id: uuid.UUID,
    data: bytes,
    content_type: str,
) -> None:
    """Keep the patient's recording so the doctor can hear the original words."""
    report = _own_report(session, access, report_id)
    mime = content_type.split(";")[0].strip().lower()
    if mime not in AUDIO_TYPES:
        raise AppError(415, "unsupported_audio", "Send webm, ogg, mp4, mp3 or wav audio.")
    if not data:
        raise AppError(422, "empty_audio", "The recording is empty.")
    if len(data) > settings.report_audio_max_bytes:
        raise AppError(413, "audio_too_large", "The recording is too long.")
    if report.rejected_at is not None:
        raise AppError(409, "report_rejected", "This report was not confirmed.")
    if report.audio_url is not None:
        raise AppError(409, "audio_exists", "This report already has a recording.")
    folder = Path(settings.media_dir) / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{report.id}.{AUDIO_TYPES[mime]}").write_bytes(data)
    report.audio_url = f"/api/v1/reports/{report.id}/audio"
    message_id = (report.report_json or {}).get("message_id")
    message = session.get(Message, uuid.UUID(message_id)) if message_id else None
    if message is not None:  # the audio arrived after the patient said yes
        message.audio_url = report.audio_url
    session.flush()


# --- Doctor: list, read, mark seen ----------------------------------------------------------


def _item_fields(report: Report, discharge: Discharge, patient: Patient) -> dict[str, Any]:
    data = report.report_json or {}
    day = data.get("recovery_day")
    return {
        "id": report.id,
        "discharge_id": discharge.id,
        "patient_name": patient.name,
        "language": report.detected_language,
        "type": report.type,
        "status": report.status,
        "reported_by": report.reported_by,
        "summary_en": str(data.get("summary_en") or report.translation_en or ""),
        "recovery_day": int(day) if day is not None else recovery_day(discharge, report.created_at),
        "created_at": report.created_at,
    }


def list_reports(
    session: Session,
    hospital_id: uuid.UUID,
    status: ReportStatus | None = None,
    report_type: ReportType | None = None,
    discharge_id: uuid.UUID | None = None,
) -> list[ReportListItem]:
    query = (
        select(Report, Discharge, Patient)
        .join(Discharge, Discharge.id == Report.discharge_id)
        .join(Patient, Patient.id == Discharge.patient_id)
        .where(Report.hospital_id == hospital_id, Report.confirmed_by_patient.is_(True))
    )
    if status is not None:
        query = query.where(Report.status == status)
    if report_type is not None:
        query = query.where(Report.type == report_type)
    if discharge_id is not None:
        query = query.where(Report.discharge_id == discharge_id)
    items = [ReportListItem(**_item_fields(r, d, p)) for r, d, p in session.execute(query).all()]
    items.sort(key=lambda i: -i.created_at.timestamp())
    items.sort(key=lambda i: (TYPE_ORDER[i.type], i.status is not ReportStatus.new))
    return items


def _doctor_report(session: Session, hospital_id: uuid.UUID, report_id: uuid.UUID) -> Report:
    report = session.get(Report, report_id)
    # Unconfirmed reports never reach the doctor.
    if report is None or report.hospital_id != hospital_id or not report.confirmed_by_patient:
        raise not_found("Report")
    return report


def get_report(session: Session, hospital_id: uuid.UUID, report_id: uuid.UUID) -> ReportDetail:
    report = _doctor_report(session, hospital_id, report_id)
    discharge, patient, template = _episode(session, report.discharge_id)
    data = report.report_json or {}
    flags = {f["id"]: f["label_en"] for f in template.red_flags}
    minors = {m["id"]: m["symptom_en"] for m in template.minor_symptoms}
    remedies = {m["id"]: m["remedy_en"] for m in template.minor_symptoms}
    return ReportDetail(
        **_item_fields(report, discharge, patient),
        patient_age=patient.age,
        template_name=template.name,
        discharge_status=discharge.status,
        transcript_native=report.transcript_native,
        translation_en=report.translation_en,
        read_back_native=data.get("read_back_native"),
        stt_confidence=report.stt_confidence,
        audio_url=report.audio_url,
        confidence=data.get("confidence"),
        reasons=list(data.get("reasons", [])),
        needs_review=bool(data.get("needs_review", False)),
        symptoms=[SymptomOut.model_validate(s) for s in data.get("symptoms", [])],
        red_flags=[FlagOut(id=i, label_en=flags.get(i, i)) for i in report.matched_flag_ids],
        minor_symptoms=[
            MinorOut(id=i, symptom_en=minors.get(i, i)) for i in report.matched_minor_ids
        ],
        # Shown from the template by id, whatever text was stored.
        suggested_remedies=[
            RemedyOut(minor_id=r["minor_id"], remedy_en=remedies[r["minor_id"]])
            for r in report.suggested_remedies
            if r.get("minor_id") in remedies
        ],
        medicines=[
            MedicineOut(name=m["name"], instructions=_english_medicine(m))
            for m in template.medicines
        ],
        extra_instructions=list(discharge.extra_instructions),
    )


def mark_seen(
    session: Session,
    bus: EventBus,
    hospital_id: uuid.UUID,
    doctor_id: uuid.UUID,
    report_id: uuid.UUID,
) -> ReportDetail:
    report = _doctor_report(session, hospital_id, report_id)
    if report.status is ReportStatus.new:
        report.status = ReportStatus.seen
        session.flush()
        bus.publish(
            session,
            DomainEvent(
                type=REPORT_SEEN,
                hospital_id=report.hospital_id,
                discharge_id=report.discharge_id,
                actor_type=ActorType.doctor,
                actor_id=doctor_id,
                payload={"report_id": str(report.id)},
            ),
        )
    return get_report(session, hospital_id, report_id)


def audio_file(
    session: Session, settings: Settings, hospital_id: uuid.UUID, report_id: uuid.UUID
) -> tuple[Path, str]:
    report = _doctor_report(session, hospital_id, report_id)
    folder = Path(settings.media_dir) / "reports"
    for path in folder.glob(f"{report.id}.*"):
        return path, MEDIA_TYPES.get(path.suffix.lstrip("."), "application/octet-stream")
    raise not_found("Recording")
