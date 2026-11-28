"""Dictated discharge: extract a card, save it as a draft, and approve it.

Approval is the safety gate: the server recomputes unclear fields on every save and on
approve, and refuses while any remain. Approve is idempotent: a double tap returns the
first result and publishes discharge.approved exactly once.
"""

import re
import uuid
from datetime import UTC, date, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.orm import Session

from app.ai.registry import run_task
from app.ai.tasks.common import TemplateRef
from app.ai.tasks.extract_discharge.schema import ExtractDischargeInput
from app.core.context import Staff
from app.core.errors import AppError, not_found
from app.core.events import DISCHARGE_APPROVED, DomainEvent, EventBus
from app.core.models import (
    ActorType,
    Carer,
    Discharge,
    DischargeStatus,
    Patient,
    Report,
    ReportStatus,
    Template,
)
from app.modules.discharges.schemas import (
    ApproveResult,
    DischargeCard,
    DischargeListItem,
    DischargeOut,
    ExtractResponse,
    PatientRef,
    TemplateOption,
)
from app.providers.registry import ProviderRegistry
from app.rules.extractors import medicine_issue
from app.rules.lexicon import get_lexicon
from app.rules.text import normalise

REQUIRED = ("patient_name", "age", "template_name", "language")
PHONE = re.compile(r"^\+91[6-9]\d{9}$")
# Dashboard order: alerts first, then patients who need follow-up.
STATUS_ORDER = {
    DischargeStatus.alert: 0,
    DischargeStatus.needs_followup: 1,
    DischargeStatus.sent: 2,
    DischargeStatus.understood: 3,
    DischargeStatus.draft: 4,
    DischargeStatus.closed: 5,
}


def today() -> date:
    return datetime.now(UTC).date()


def recovery_day(discharged_on: date) -> int:
    """Day 1 is the day of discharge."""
    return max(1, (today() - discharged_on).days + 1)


# --- Templates available to this doctor ----------------------------------------


def template_options(session: Session, hospital_id: uuid.UUID) -> list[TemplateOption]:
    latest = (
        select(Template.id, func.max(Template.version).label("version"))
        .where(Template.hospital_id == hospital_id)
        .group_by(Template.id)
        .subquery()
    )
    rows = session.scalars(
        select(Template).join(
            latest, (Template.id == latest.c.id) & (Template.version == latest.c.version)
        )
    )
    return [
        TemplateOption(id=t.id, version=t.version, name=t.name, condition=t.condition) for t in rows
    ]


def _resolve_template(card: DischargeCard, options: list[TemplateOption]) -> TemplateOption | None:
    """Fill template_id from the name or the name from the id; None if neither matches."""
    match = None
    if card.template_id is not None:
        match = next((o for o in options if o.id == card.template_id), None)
    elif card.template_name:
        wanted = normalise(card.template_name)
        match = next((o for o in options if normalise(o.name) == wanted), None)
    card.template_id = match.id if match else None
    card.template_name = match.name if match else card.template_name
    return match


# --- Validation: the approval gate ------------------------------------------------


def unclear_fields(card: DischargeCard, options: list[TemplateOption]) -> list[str]:
    """Everything the doctor must fix before this card can reach a patient."""
    out: list[str] = []
    if not (card.patient_name or "").strip():
        out.append("patient_name")
    if card.age is None:
        out.append("age")
    if _resolve_template(card, options) is None:
        out.append("template_name")
    if card.language not in get_lexicon().languages:
        out.append("language")
    if card.carer_phone and not PHONE.match(card.carer_phone.replace(" ", "")):
        out.append("carer_phone")
    lex = get_lexicon()
    for i, extra in enumerate(card.extra_instructions):
        if not extra.strip() or medicine_issue(normalise(extra), lex):
            out.append(f"extra_instructions[{i}]")
    return out


def _clean(card: DischargeCard) -> DischargeCard:
    card.patient_name = (card.patient_name or "").strip() or None
    card.extra_instructions = [e.strip() for e in card.extra_instructions]
    if card.carer_phone:
        digits = re.sub(r"\D", "", card.carer_phone)
        card.carer_phone = f"+91{digits[-10:]}" if len(digits) >= 10 else card.carer_phone.strip()
    return card


# --- Patients -----------------------------------------------------------------------


def _find_patient(session: Session, hospital_id: uuid.UUID, name: str) -> Patient | None:
    return session.scalars(
        select(Patient)
        .where(Patient.hospital_id == hospital_id, func.lower(Patient.name) == name.strip().lower())
        .order_by(Patient.created_at.desc())
    ).first()


def _patient_ref(p: Patient) -> PatientRef:
    return PatientRef(id=p.id, name=p.name, age=p.age, preferred_language=p.preferred_language)


def _upsert_patient(session: Session, staff: Staff, card: DischargeCard) -> Patient:
    assert card.patient_name
    patient = _find_patient(session, staff.hospital_id, card.patient_name)
    if patient is None:
        patient = Patient(
            hospital_id=staff.hospital_id,
            name=card.patient_name,
            age=card.age,
            sex="unknown",
            preferred_language=card.language or "en",
        )
        session.add(patient)
        session.flush()
    else:
        if card.age is not None:
            patient.age = card.age
        if card.language in get_lexicon().languages:
            patient.preferred_language = card.language
    if card.carer_phone and PHONE.match(card.carer_phone):
        exists = session.scalar(
            select(Carer).where(Carer.patient_id == patient.id, Carer.phone == card.carer_phone)
        )
        if exists is None:
            session.add(
                Carer(
                    hospital_id=staff.hospital_id,
                    patient_id=patient.id,
                    name="Carer",
                    relation="family",
                    phone=card.carer_phone,
                    preferred_language=patient.preferred_language,
                )
            )
    return patient


# --- Reading a discharge back as a card ---------------------------------------------


def _load(session: Session, staff: Staff, discharge_id: uuid.UUID) -> Discharge:
    discharge = session.get(Discharge, discharge_id)
    if discharge is None or discharge.hospital_id != staff.hospital_id:
        raise not_found("Discharge")
    return discharge


def _card_of(session: Session, d: Discharge) -> tuple[DischargeCard, Patient]:
    patient = session.get(Patient, d.patient_id)
    template = session.get(Template, (d.template_id, d.template_version))
    assert patient is not None and template is not None
    carer = session.scalars(
        select(Carer)
        .where(Carer.patient_id == patient.id, Carer.phone.is_not(None))
        .order_by(Carer.created_at.desc())
    ).first()
    card = DischargeCard(
        patient_name=patient.name,
        age=patient.age,
        template_id=template.id,
        template_name=template.name,
        side=d.side,
        language=patient.preferred_language,
        carer_phone=carer.phone if carer else None,
        extra_instructions=list(d.extra_instructions),
    )
    return card, patient


def to_out(session: Session, d: Discharge) -> DischargeOut:
    card, patient = _card_of(session, d)
    options = template_options(session, d.hospital_id)
    # The pinned version stays valid even if a newer version exists.
    options = [o for o in options if o.id != d.template_id] + [
        TemplateOption(
            id=d.template_id,
            version=d.template_version,
            name=card.template_name or "",
            condition="",
        )
    ]
    return DischargeOut(
        id=d.id,
        status=d.status,
        card=card,
        unclear_fields=unclear_fields(card.model_copy(), options),
        patient=_patient_ref(patient),
        template_version=d.template_version,
        discharged_on=d.discharged_on,
        recovery_day=recovery_day(d.discharged_on),
        approved_at=d.approved_at,
        created_at=d.created_at,
    )


# --- Use cases ----------------------------------------------------------------------


async def extract(
    session: Session, staff: Staff, providers: ProviderRegistry, transcript: str
) -> ExtractResponse:
    options = template_options(session, staff.hospital_id)
    result = await run_task(
        providers,
        "extract_discharge",
        ExtractDischargeInput(
            transcript=transcript,
            templates=[TemplateRef(name=o.name, condition=o.condition) for o in options],
        ),
    )
    extracted = result.output
    card = _clean(
        DischargeCard(
            patient_name=extracted.patient_name,
            age=extracted.age,
            template_name=extracted.template_name,
            side=extracted.side,
            language=extracted.language,
            carer_phone=extracted.carer_phone,
            extra_instructions=extracted.extra_instructions,
        )
    )
    unclear = unclear_fields(card, options)
    # Keep anything the extractor itself was unsure about (a real LLM may flag more).
    unclear += [f for f in extracted.unclear_fields if f not in unclear]
    matched = (
        _find_patient(session, staff.hospital_id, card.patient_name) if card.patient_name else None
    )
    return ExtractResponse(
        transcript=transcript,
        card=card,
        unclear_fields=unclear,
        matched_patient=_patient_ref(matched) if matched else None,
        source=result.source,
        needs_review=result.needs_review,
    )


def create_draft(session: Session, staff: Staff, card: DischargeCard) -> DischargeOut:
    card = _clean(card)
    options = template_options(session, staff.hospital_id)
    template = _resolve_template(card, options)
    if not card.patient_name or template is None:
        raise AppError(
            422,
            "missing_required",
            "A draft needs at least the patient's name and a template.",
            {"unclear_fields": unclear_fields(card, options)},
        )
    patient = _upsert_patient(session, staff, card)
    discharge = Discharge(
        hospital_id=staff.hospital_id,
        patient_id=patient.id,
        doctor_id=staff.id,
        template_id=template.id,
        template_version=template.version,
        side=card.side,
        extra_instructions=card.extra_instructions,
        discharged_on=today(),
        status=DischargeStatus.draft,
    )
    session.add(discharge)
    session.flush()
    return to_out(session, discharge)


def update_draft(
    session: Session, staff: Staff, discharge_id: uuid.UUID, card: DischargeCard
) -> DischargeOut:
    discharge = _load(session, staff, discharge_id)
    if discharge.status is not DischargeStatus.draft:
        raise AppError(409, "not_draft", "This discharge was already sent and cannot be edited.")
    card = _clean(card)
    options = template_options(session, staff.hospital_id)
    template = _resolve_template(card, options)
    if not card.patient_name or template is None:
        raise AppError(
            422,
            "missing_required",
            "A draft needs at least the patient's name and a template.",
            {"unclear_fields": unclear_fields(card, options)},
        )
    patient = _upsert_patient(session, staff, card)
    discharge.patient_id = patient.id
    discharge.template_id = template.id
    discharge.template_version = template.version
    discharge.side = card.side
    discharge.extra_instructions = card.extra_instructions
    session.flush()
    return to_out(session, discharge)


def approve(
    session: Session, staff: Staff, bus: EventBus, discharge_id: uuid.UUID
) -> ApproveResult:
    discharge = _load(session, staff, discharge_id)
    if discharge.status is not DischargeStatus.draft:
        return ApproveResult(outcome="already_approved", discharge=to_out(session, discharge))

    current = to_out(session, discharge)
    if current.unclear_fields:
        raise AppError(
            422,
            "unclear_fields",
            "Fix the highlighted fields before approving.",
            {"unclear_fields": current.unclear_fields},
        )

    # Atomic claim: only one request can move draft -> sent, so a double tap sends once.
    result = session.execute(
        update(Discharge)
        .where(Discharge.id == discharge.id, Discharge.status == DischargeStatus.draft)
        .values(status=DischargeStatus.sent, approved_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    claimed = cast(CursorResult[Any], result).rowcount
    session.refresh(discharge)
    if not claimed:
        return ApproveResult(outcome="already_approved", discharge=to_out(session, discharge))

    carers = session.scalars(select(Carer.id).where(Carer.patient_id == discharge.patient_id)).all()
    bus.publish(
        session,
        DomainEvent(
            type=DISCHARGE_APPROVED,
            hospital_id=discharge.hospital_id,
            discharge_id=discharge.id,
            actor_type=ActorType.doctor,
            actor_id=staff.id,
            payload={
                "patient_id": str(discharge.patient_id),
                "carer_ids": [str(c) for c in carers],
                "template_id": str(discharge.template_id),
                "template_version": discharge.template_version,
                "language": current.patient.preferred_language,
                "extra_instructions": list(discharge.extra_instructions),
            },
        ),
    )
    return ApproveResult(outcome="approved", discharge=to_out(session, discharge))


def get_discharge(session: Session, staff: Staff, discharge_id: uuid.UUID) -> DischargeOut:
    return to_out(session, _load(session, staff, discharge_id))


def _report_summary(
    session: Session, hospital_id: uuid.UUID
) -> dict[uuid.UUID, tuple[int, Report]]:
    """Per discharge: confirmed reports not yet seen, and the latest confirmed report."""
    rows = session.scalars(
        select(Report)
        .where(Report.hospital_id == hospital_id, Report.confirmed_by_patient.is_(True))
        .order_by(Report.created_at)
    )
    out: dict[uuid.UUID, tuple[int, Report]] = {}
    for r in rows:
        unseen = out.get(r.discharge_id, (0, r))[0] + (r.status is ReportStatus.new)
        out[r.discharge_id] = (unseen, r)
    return out


def list_discharges(
    session: Session, staff: Staff, status: DischargeStatus | None, q: str | None = None
) -> list[DischargeListItem]:
    query = (
        select(Discharge, Patient, Template)
        .join(Patient, Patient.id == Discharge.patient_id)
        .join(
            Template,
            (Template.id == Discharge.template_id)
            & (Template.version == Discharge.template_version),
        )
        .where(Discharge.hospital_id == staff.hospital_id)
    )
    if status is not None:
        query = query.where(Discharge.status == status)
    if q and q.strip():
        query = query.where(func.lower(Patient.name).contains(q.strip().lower()))
    rows = session.execute(query).all()
    reports = _report_summary(session, staff.hospital_id)
    items = [
        DischargeListItem(
            id=d.id,
            status=d.status,
            patient_name=p.name,
            age=p.age,
            language=p.preferred_language,
            template_name=t.name,
            discharged_on=d.discharged_on,
            recovery_day=recovery_day(d.discharged_on),
            approved_at=d.approved_at,
            new_reports=reports[d.id][0] if d.id in reports else 0,
            latest_report_id=reports[d.id][1].id if d.id in reports else None,
            latest_report_type=reports[d.id][1].type if d.id in reports else None,
        )
        for d, p, t in rows
    ]
    items.sort(
        key=lambda i: (
            STATUS_ORDER[i.status],
            -(i.approved_at or datetime.min.replace(tzinfo=UTC)).timestamp(),
        )
    )
    return items
