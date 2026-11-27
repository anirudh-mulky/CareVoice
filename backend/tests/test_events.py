import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import models as m
from app.core.db import Database
from app.core.events import (
    ALL,
    DISCHARGE_APPROVED,
    REPORT_CONFIRMED,
    DomainEvent,
    EventBus,
)


def event_rows(db: Database) -> list[m.Event]:
    with db.session() as s:
        return list(s.scalars(select(m.Event).order_by(m.Event.created_at)))


def test_bus_delivers_event_to_listener_and_writes_it(db: Database, bus: EventBus) -> None:
    received: list[DomainEvent] = []
    bus.subscribe(DISCHARGE_APPROVED, lambda event, _session: received.append(event))

    with db.session() as s:
        bus.publish(s, DomainEvent(type=DISCHARGE_APPROVED, payload={"patient": "Ramesh"}))

    assert [e.payload for e in received] == [{"patient": "Ramesh"}]
    rows = event_rows(db)
    assert len(rows) == 1
    assert rows[0].type == DISCHARGE_APPROVED
    assert rows[0].payload == {"patient": "Ramesh"}
    assert rows[0].id == received[0].id


def test_listener_only_gets_its_event_type(db: Database, bus: EventBus) -> None:
    received: list[str] = []
    bus.subscribe(DISCHARGE_APPROVED, lambda event, _s: received.append(event.type))
    with db.session() as s:
        bus.publish(s, DomainEvent(type=REPORT_CONFIRMED))
    assert received == []
    assert len(event_rows(db)) == 1  # still audited with no listener


def test_wildcard_listener_sees_everything(db: Database, bus: EventBus) -> None:
    seen: list[str] = []
    bus.subscribe(ALL, lambda event, _s: seen.append(event.type))
    with db.session() as s:
        bus.publish(s, DomainEvent(type=DISCHARGE_APPROVED))
        bus.publish(s, DomainEvent(type=REPORT_CONFIRMED))
    assert seen == [DISCHARGE_APPROVED, REPORT_CONFIRMED]


def test_listener_writes_share_the_publishers_transaction(db: Database, bus: EventBus) -> None:
    def on_approved(_event: DomainEvent, session: Session) -> None:
        session.add(m.Hospital(name="Written by listener", city="Mysuru"))

    bus.subscribe(DISCHARGE_APPROVED, on_approved)
    with db.session() as s:
        bus.publish(s, DomainEvent(type=DISCHARGE_APPROVED))
    with db.session() as s:
        assert s.scalar(select(func.count()).select_from(m.Hospital)) == 1


def test_failing_listener_rolls_back_event_and_state(db: Database, bus: EventBus) -> None:
    def broken(_event: DomainEvent, _session: Session) -> None:
        raise RuntimeError("listener failed")

    bus.subscribe(DISCHARGE_APPROVED, broken)
    with pytest.raises(RuntimeError), db.session() as s:
        s.add(m.Hospital(name="Should vanish", city="Bengaluru"))
        bus.publish(s, DomainEvent(type=DISCHARGE_APPROVED))

    assert event_rows(db) == []
    with db.session() as s:
        assert s.scalar(select(func.count()).select_from(m.Hospital)) == 0
