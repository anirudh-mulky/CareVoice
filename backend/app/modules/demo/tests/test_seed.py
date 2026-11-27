from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import models as m
from app.core.db import Database
from app.core.events import EventBus
from app.main import create_app
from app.modules.demo import service
from app.modules.demo.service import seed_id
from tests.support import make_settings

LANGS = {"en", "kn", "hi", "ta"}


def seeded_counts(db: Database) -> dict[str, int]:
    with db.session() as s:
        return service.counts(s)


def test_seed_inserts_the_spec_demo_data(db: Database, bus: EventBus) -> None:
    assert service.seed_if_empty(db, bus) is True
    with db.session() as s:
        assert [h.name for h in s.scalars(select(m.Hospital))] == ["CareVoice Demo Hospital"]
        doctors = s.scalars(select(m.User).where(m.User.role == m.Role.doctor)).all()
        assert [d.name for d in doctors] == ["Dr. Priya"]

        patients = {p.name: p for p in s.scalars(select(m.Patient))}
        assert {n: (p.age, p.preferred_language) for n, p in patients.items()} == {
            "Ramesh": (68, "kn"),
            "Sunita": (29, "hi"),
            "Murugan": (55, "ta"),
        }
        # Every patient has a carer.
        carers = s.scalars(select(m.Carer)).all()
        assert {c.patient_id for c in carers} == {p.id for p in patients.values()}

        assert {t.name for t in s.scalars(select(m.Template))} == {"Cataract surgery", "C-section"}

        reports = s.scalars(select(m.Report)).all()
        assert sorted(r.type.value for r in reports) == ["alert", "minor"]
        assert all(r.status is m.ReportStatus.new for r in reports)


def test_ramesh_is_left_undischarged_for_the_live_demo(db: Database, bus: EventBus) -> None:
    service.seed_if_empty(db, bus)
    with db.session() as s:
        ramesh = seed_id("patient:ramesh")
        assert s.scalars(select(m.Discharge).where(m.Discharge.patient_id == ramesh)).all() == []


def test_templates_meet_the_seed_rules(db: Database, bus: EventBus) -> None:
    service.seed_if_empty(db, bus)
    with db.session() as s:
        for tpl in s.scalars(select(m.Template)):
            assert 4 <= len(tpl.red_flags) <= 6, tpl.name
            assert 2 <= len(tpl.minor_symptoms) <= 3, tpl.name
            for item in [*tpl.red_flags, *tpl.minor_symptoms]:
                assert set(item["keywords"]) == LANGS, item["id"]
                assert all(item["keywords"][lang] for lang in LANGS), item["id"]


def test_translations_cover_every_flag_and_remedy(db: Database, bus: EventBus) -> None:
    service.seed_if_empty(db, bus)
    with db.session() as s:
        translations = s.scalars(select(m.TemplateTranslation)).all()
        assert {(t.language) for t in translations} == {"kn", "ta", "hi"}
        for tr in translations:
            tpl = s.get(m.Template, (tr.template_id, tr.version))
            assert tpl is not None
            assert [f["id"] for f in tr.content["red_flags"]] == [f["id"] for f in tpl.red_flags]
            assert [x["id"] for x in tr.content["minor_symptoms"]] == [
                x["id"] for x in tpl.minor_symptoms
            ]
            assert tr.verified_by is None  # needs a native speaker before real use


def test_seeded_remedies_come_from_the_template(db: Database, bus: EventBus) -> None:
    service.seed_if_empty(db, bus)
    with db.session() as s:
        report = s.scalars(select(m.Report).where(m.Report.type == m.ReportType.minor)).one()
        discharge = s.get(m.Discharge, report.discharge_id)
        assert discharge is not None
        tpl = s.get(m.Template, (discharge.template_id, discharge.template_version))
        assert tpl is not None
        template_remedies = {ms["id"]: ms["remedy_en"] for ms in tpl.minor_symptoms}
        for remedy in report.suggested_remedies:
            assert remedy["remedy_en"] == template_remedies[remedy["minor_id"]]


def test_seeding_is_idempotent(db: Database, bus: EventBus) -> None:
    assert service.seed_if_empty(db, bus) is True
    first = seeded_counts(db)
    assert service.seed_if_empty(db, bus) is False
    assert service.seed_if_empty(db, bus) is False
    assert seeded_counts(db) == first


def test_seed_writes_history_and_a_seeded_event(db: Database, bus: EventBus) -> None:
    service.seed_if_empty(db, bus)
    with db.session() as s:
        types = list(s.scalars(select(m.Event.type)))
    assert "demo.seeded" in types
    assert types.count("discharge.approved") == 2
    assert "report.alert" in types


def test_seed_does_not_trigger_domain_listeners(db: Database, bus: EventBus) -> None:
    delivered: list[str] = []
    bus.subscribe("discharge.approved", lambda e, _s: delivered.append(e.type))
    service.seed_if_empty(db, bus)
    assert delivered == []


def test_reset_restores_seed_data(db: Database, bus: EventBus) -> None:
    service.seed_if_empty(db, bus)
    original = seeded_counts(db)
    with db.session() as s:
        ramesh = s.get(m.Patient, seed_id("patient:ramesh"))
        assert ramesh is not None
        ramesh.name = "Changed"
        s.delete(s.scalars(select(m.Report)).first())
        s.add(m.Hospital(name="Extra", city="Chennai"))

    counts = service.reset(db, bus)

    assert counts["hospitals"] == original["hospitals"]
    assert counts["reports"] == original["reports"]
    with db.session() as s:
        ramesh = s.get(m.Patient, seed_id("patient:ramesh"))
        assert ramesh is not None
        assert ramesh.name == "Ramesh"  # same stable id after reset


def test_app_seeds_on_first_start(client: TestClient) -> None:
    db: Database = client.app.state.db  # type: ignore[attr-defined]
    assert seeded_counts(db)["patients"] == 3


def test_reset_endpoint(client: TestClient) -> None:
    db: Database = client.app.state.db  # type: ignore[attr-defined]
    with db.session() as s:
        s.add(m.Hospital(name="Extra", city="Chennai"))

    res = client.post("/api/v1/demo/reset")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "reset"
    assert body["counts"]["hospitals"] == 1
    assert body["counts"]["patients"] == 3
    assert client.get("/api/v1/health").json()["status"] == "ok"


@pytest.mark.parametrize("flag", ["false", "0"])
def test_reset_endpoint_is_off_when_demo_endpoints_disabled(tmp_path: Path, flag: str) -> None:
    settings = make_settings(tmp_path, demo_endpoints=flag)
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/v1/demo/reset").status_code == 404
