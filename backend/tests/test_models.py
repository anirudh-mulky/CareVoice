import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.core import models as m
from app.core.db import Database

EXPECTED_TABLES = {
    "hospitals",
    "users",
    "patients",
    "carers",
    "templates",
    "template_translations",
    "discharges",
    "messages",
    "reports",
    "events",
    "scheduled_jobs",
}


def make_graph(db: Database) -> dict[str, uuid.UUID]:
    """One row in every table, wired together the way the app uses them."""
    ids: dict[str, uuid.UUID] = {}
    with db.session() as s:
        h = m.Hospital(name="Test Hospital", city="Bengaluru", default_languages=["en", "kn"])
        s.add(h)
        s.flush()
        doctor = m.User(hospital_id=h.id, name="Dr. Test", role=m.Role.doctor)
        patient = m.Patient(
            hospital_id=h.id, name="Ramesh", age=68, sex="male", preferred_language="kn"
        )
        s.add_all([doctor, patient])
        s.flush()
        s.add(
            m.Carer(
                hospital_id=h.id,
                patient_id=patient.id,
                name="Kiran",
                relation="son",
                preferred_language="kn",
            )
        )
        tpl = m.Template(
            hospital_id=h.id,
            doctor_id=doctor.id,
            name="Cataract",
            condition="cataract",
            red_flags=[{"id": "rf_redness", "label_en": "Red eye", "keywords": {"kn": ["ಕೆಂಪು"]}}],
        )
        s.add(tpl)
        s.flush()
        s.add(
            m.TemplateTranslation(
                template_id=tpl.id,
                version=tpl.version,
                language="kn",
                hospital_id=h.id,
                content={"name": "ಕಣ್ಣಿನ ಪೊರೆ"},
            )
        )
        d = m.Discharge(
            hospital_id=h.id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            template_id=tpl.id,
            template_version=tpl.version,
            discharged_on=date(2026, 11, 27),
        )
        s.add(d)
        s.flush()
        s.add_all(
            [
                m.Message(
                    hospital_id=h.id,
                    discharge_id=d.id,
                    direction=m.MessageDirection.to_patient,
                    kind=m.MessageKind.instructions,
                    text_native="ನಮಸ್ಕಾರ",
                    language="kn",
                ),
                m.Report(
                    hospital_id=h.id,
                    discharge_id=d.id,
                    transcript_native="ಕಣ್ಣು ಕೆಂಪಾಗಿದೆ",
                    detected_language="kn",
                    type=m.ReportType.alert,
                    matched_flag_ids=["rf_redness"],
                ),
                m.ScheduledJob(
                    hospital_id=h.id,
                    discharge_id=d.id,
                    kind="reminder",
                    due_at=datetime(2026, 11, 29, 9, tzinfo=UTC),
                ),
                m.Event(hospital_id=h.id, discharge_id=d.id, type="discharge.approved"),
            ]
        )
        ids.update(hospital=h.id, template=tpl.id, discharge=d.id, patient=patient.id)
    return ids


def test_all_eleven_tables_exist(db: Database) -> None:
    assert set(inspect(db.engine).get_table_names()) == EXPECTED_TABLES


def test_every_tenant_table_carries_hospital_id(db: Database) -> None:
    insp = inspect(db.engine)
    for table in EXPECTED_TABLES - {"hospitals"}:
        columns = {c["name"] for c in insp.get_columns(table)}
        assert "hospital_id" in columns, table


def test_full_graph_round_trips_with_defaults(db: Database) -> None:
    ids = make_graph(db)
    with db.session() as s:
        d = s.get(m.Discharge, ids["discharge"])
        assert d is not None
        assert d.status is m.DischargeStatus.draft
        assert d.extra_instructions == []
        assert isinstance(d.id, uuid.UUID)

        report = s.scalars(select(m.Report)).one()
        assert report.status is m.ReportStatus.new
        assert report.confirmed_by_patient is False
        assert report.transcript_native == "ಕಣ್ಣು ಕೆಂಪಾಗಿದೆ"  # unicode survives

        tpl = s.get(m.Template, (ids["template"], 1))
        assert tpl is not None
        assert tpl.red_flags[0]["keywords"]["kn"] == ["ಕೆಂಪು"]

        job = s.scalars(select(m.ScheduledJob)).one()
        assert job.status is m.JobStatus.pending
        assert job.attempts == 0


def test_templates_are_versioned_by_id_and_version(db: Database) -> None:
    ids = make_graph(db)
    with db.session() as s:
        v1 = s.get(m.Template, (ids["template"], 1))
        assert v1 is not None
        s.add(
            m.Template(
                id=v1.id,
                version=2,
                hospital_id=v1.hospital_id,
                name=v1.name,
                condition=v1.condition,
            )
        )
    with db.session() as s:
        versions = s.scalars(
            select(m.Template.version).where(m.Template.id == ids["template"])
        ).all()
        assert sorted(versions) == [1, 2]


def test_discharge_must_pin_an_existing_template_version(db: Database) -> None:
    ids = make_graph(db)
    with pytest.raises(IntegrityError), db.session() as s:
        d = s.get(m.Discharge, ids["discharge"])
        assert d is not None
        s.add(
            m.Discharge(
                hospital_id=ids["hospital"],
                patient_id=ids["patient"],
                doctor_id=d.doctor_id,
                template_id=ids["template"],
                template_version=99,
                discharged_on=date(2026, 11, 27),
            )
        )


def test_enums_are_stored_as_their_values(db: Database) -> None:
    make_graph(db)
    with db.engine.connect() as conn:
        status = conn.exec_driver_sql("SELECT status FROM discharges").scalar()
    assert status == "draft"


def test_events_are_append_only(db: Database) -> None:
    make_graph(db)
    with pytest.raises(m.AppendOnlyError), db.session() as s:
        event = s.scalars(select(m.Event)).one()
        event.type = "tampered"
    with pytest.raises(m.AppendOnlyError), db.session() as s:
        s.delete(s.scalars(select(m.Event)).one())
    with db.session() as s:
        assert s.scalars(select(m.Event.type)).one() == "discharge.approved"
