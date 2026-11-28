"""Demo data: seed from app/seed/*.json on first start, and reset to that seed.

Seed records use readable keys ("patient:ramesh") that map to stable UUIDs, so ids
and patient links are identical after every reset. All data is synthetic.
"""

import json
import uuid
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import models as m
from app.core.db import Base, Database
from app.core.events import (
    DEMO_DAY_ADVANCED,
    DEMO_RESET,
    DEMO_SEEDED,
    REMINDER_DUE,
    DomainEvent,
    EventBus,
)

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"
SEED_NAMESPACE = uuid.UUID("6f1c2b7e-3d4a-4c1e-9b8a-0c5e7d2f1a90")
CONSENT_VERSION = "demo-v1"

COUNTED_TABLES: dict[str, type[Base]] = {
    "hospitals": m.Hospital,
    "users": m.User,
    "patients": m.Patient,
    "carers": m.Carer,
    "templates": m.Template,
    "template_translations": m.TemplateTranslation,
    "discharges": m.Discharge,
    "messages": m.Message,
    "reports": m.Report,
    "events": m.Event,
    "scheduled_jobs": m.ScheduledJob,
    "access_tokens": m.AccessToken,
}


def seed_id(key: str) -> uuid.UUID:
    """Stable UUID for a seed key, e.g. seed_id("patient:ramesh")."""
    return uuid.uuid5(SEED_NAMESPACE, key)


def _load(name: str, seed_dir: Path) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads((seed_dir / f"{name}.json").read_text("utf-8"))
    return data


def is_seeded(session: Session) -> bool:
    return (session.scalar(select(func.count()).select_from(m.Hospital)) or 0) > 0


def counts(session: Session) -> dict[str, int]:
    return {
        name: session.scalar(select(func.count()).select_from(model)) or 0
        for name, model in COUNTED_TABLES.items()
    }


def seed(session: Session, now: datetime | None = None, seed_dir: Path = SEED_DIR) -> None:
    """Insert the demo data. Call on an empty database (see seed_if_empty)."""
    now = now or datetime.now(UTC)

    for h in _load("hospitals", seed_dir):
        session.add(
            m.Hospital(
                id=seed_id(h["key"]),
                name=h["name"],
                city=h["city"],
                phone=h.get("phone"),
                default_languages=h["default_languages"],
            )
        )
    session.flush()

    for u in _load("users", seed_dir):
        session.add(
            m.User(
                id=seed_id(u["key"]),
                hospital_id=seed_id(u["hospital"]),
                name=u["name"],
                role=m.Role(u["role"]),
                phone=u.get("phone"),
                email=u.get("email"),
            )
        )
    session.flush()

    templates: dict[str, dict[str, Any]] = {}
    hospital_of_template: dict[str, uuid.UUID] = {}
    for t in _load("templates", seed_dir):
        templates[t["key"]] = t
        hospital_of_template[t["key"]] = seed_id(t["hospital"])
        session.add(
            m.Template(
                id=seed_id(t["key"]),
                version=t["version"],
                hospital_id=seed_id(t["hospital"]),
                doctor_id=seed_id(t["doctor"]),
                name=t["name"],
                condition=t["condition"],
                medicines=t["medicines"],
                dos=t["dos"],
                donts=t["donts"],
                red_flags=t["red_flags"],
                minor_symptoms=t["minor_symptoms"],
                reminders=t["reminders"],
                follow_up_day=t.get("follow_up_day"),
            )
        )
    session.flush()

    for tr in _load("template_translations", seed_dir):
        session.add(
            m.TemplateTranslation(
                template_id=seed_id(tr["template"]),
                version=tr["version"],
                language=tr["language"],
                hospital_id=hospital_of_template[tr["template"]],
                content=tr["content"],
                verified_by=tr.get("verified_by"),
            )
        )

    hospital_of_patient: dict[str, uuid.UUID] = {}
    patients = _load("patients", seed_dir)
    for p in patients:
        hospital_of_patient[p["key"]] = seed_id(p["hospital"])
        session.add(
            m.Patient(
                id=seed_id(p["key"]),
                hospital_id=seed_id(p["hospital"]),
                name=p["name"],
                age=p["age"],
                sex=p["sex"],
                phone=p.get("phone"),
                preferred_language=p["preferred_language"],
                consent_at=now - timedelta(days=5) if p.get("consented") else None,
                consent_version=CONSENT_VERSION if p.get("consented") else None,
            )
        )
    session.flush()

    for p in patients:
        for c in p.get("carers", []):
            session.add(
                m.Carer(
                    id=seed_id(c["key"]),
                    hospital_id=seed_id(p["hospital"]),
                    patient_id=seed_id(p["key"]),
                    name=c["name"],
                    relation=c["relation"],
                    phone=c.get("phone"),
                    preferred_language=c["preferred_language"],
                )
            )
    session.flush()

    for d in _load("discharges", seed_dir):
        _seed_discharge(session, d, templates, hospital_of_patient, now)
    session.flush()


def _seed_discharge(
    session: Session,
    d: dict[str, Any],
    templates: dict[str, dict[str, Any]],
    hospital_of_patient: dict[str, uuid.UUID],
    now: datetime,
) -> None:
    hospital_id = hospital_of_patient[d["patient"]]
    discharge_id = seed_id(d["key"])
    discharged_on = now.date() - timedelta(days=d["discharged_days_ago"])
    approved_at = datetime.combine(discharged_on, time(11, 0), tzinfo=UTC)
    # Approval always comes before the first message, whatever the time of day now is.
    first_message = min(
        (now - timedelta(minutes=msg["minutes_ago"]) for msg in d.get("messages", [])),
        default=approved_at,
    )
    approved_at = min(approved_at, first_message - timedelta(minutes=1))
    template = templates[d["template"]]
    remedies_by_id = {ms["id"]: ms["remedy_en"] for ms in template["minor_symptoms"]}

    session.add(
        m.Discharge(
            id=discharge_id,
            hospital_id=hospital_id,
            patient_id=seed_id(d["patient"]),
            doctor_id=seed_id(d["doctor"]),
            template_id=seed_id(d["template"]),
            template_version=d["template_version"],
            extra_instructions=d["extra_instructions"],
            discharged_on=discharged_on,
            status=m.DischargeStatus(d["status"]),
            approved_at=approved_at,
            created_at=approved_at,
        )
    )
    session.flush()

    history: list[tuple[datetime, str, dict[str, Any]]] = [
        (approved_at, "discharge.approved", {"template": template["name"]}),
    ]

    for msg in d.get("messages", []):
        created = now - timedelta(minutes=msg["minutes_ago"])
        session.add(
            m.Message(
                hospital_id=hospital_id,
                discharge_id=discharge_id,
                direction=m.MessageDirection(msg["direction"]),
                kind=m.MessageKind(msg["kind"]),
                text_native=msg.get("text_native"),
                text_en=msg.get("text_en"),
                language=msg["language"],
                created_at=created,
            )
        )
        if msg["direction"] == "to_patient":
            history.append((created, "message.sent", {"kind": msg["kind"]}))

    for r in d.get("reports", []):
        created = now - timedelta(minutes=r["minutes_ago"])
        # Remedies always come from the doctor's template, looked up by minor_id.
        remedies = [
            {"minor_id": s["minor_id"], "remedy_en": remedies_by_id[s["minor_id"]]}
            for s in r.get("suggested_remedies", [])
        ]
        report_id = uuid.uuid4()
        session.add(
            m.Report(
                id=report_id,
                hospital_id=hospital_id,
                discharge_id=discharge_id,
                transcript_native=r["transcript_native"],
                detected_language=r["detected_language"],
                stt_confidence=r.get("stt_confidence"),
                translation_en=r.get("translation_en"),
                report_json=r.get("report_json", {}),
                matched_flag_ids=r.get("matched_flag_ids", []),
                matched_minor_ids=r.get("matched_minor_ids", []),
                suggested_remedies=remedies,
                type=m.ReportType(r["type"]),
                status=m.ReportStatus(r.get("status", "new")),
                confirmed_by_patient=r.get("confirmed_by_patient", False),
                created_at=created,
            )
        )
        history.append((created, "report.confirmed", {"report_id": str(report_id)}))
        if r["type"] == "alert":
            history.append((created, "report.alert", {"report_id": str(report_id)}))

    # Historical audit rows for the timeline. Written directly (not published) so that
    # listeners such as delivery do not re-send seeded messages.
    for created, event_type, payload in sorted(history, key=lambda h: h[0]):
        session.add(
            m.Event(
                hospital_id=hospital_id,
                discharge_id=discharge_id,
                type=event_type,
                payload={**payload, "seeded": True},
                created_at=created,
            )
        )


def seed_if_empty(db: Database, bus: EventBus) -> bool:
    """Seed on first start. Returns True if data was inserted. Safe to call repeatedly."""
    with db.session() as session:
        if is_seeded(session):
            return False
        seed(session)
        bus.publish(session, DomainEvent(type=DEMO_SEEDED, payload=counts(session)))
    return True


def reset(db: Database, bus: EventBus) -> dict[str, int]:
    """Drop every table, recreate it and reseed. Demo only."""
    db.engine.dispose()
    db.drop_all()
    db.create_all()
    with db.session() as session:
        seed(session)
        bus.publish(session, DomainEvent(type=DEMO_RESET))
        return counts(session)


# Episodes that are still running; "Simulate next day" moves only these.
RUNNING = (
    m.DischargeStatus.sent,
    m.DischargeStatus.understood,
    m.DischargeStatus.needs_followup,
    m.DischargeStatus.alert,
)


def advance_day(session: Session, bus: EventBus, hospital_id: uuid.UUID) -> list[dict[str, Any]]:
    """Demo "Simulate next day": every running episode is one day further into recovery.

    Moves discharged_on back a day and publishes demo.day_advanced per episode; the reminders
    module listens and sends that day's reminders. Returns one line per patient.
    """
    rows = session.execute(
        select(m.Discharge, m.Patient)
        .join(m.Patient, m.Patient.id == m.Discharge.patient_id)
        .where(m.Discharge.hospital_id == hospital_id, m.Discharge.status.in_(RUNNING))
        .order_by(m.Patient.name)
    ).all()
    today = datetime.now(UTC).date()
    out = []
    for discharge, patient in rows:
        discharge.discharged_on = discharge.discharged_on - timedelta(days=1)
        session.flush()
        day = (today - discharge.discharged_on).days + 1
        event = bus.publish(
            session,
            DomainEvent(
                type=DEMO_DAY_ADVANCED,
                hospital_id=hospital_id,
                discharge_id=discharge.id,
                payload={"recovery_day": day},
            ),
        )
        sent = session.scalar(
            select(func.count())
            .select_from(m.Event)
            .where(
                m.Event.type == REMINDER_DUE,
                m.Event.discharge_id == discharge.id,
                m.Event.created_at >= event.created_at,
            )
        )
        out.append({"patient_name": patient.name, "recovery_day": day, "reminders_sent": sent or 0})
    return out
