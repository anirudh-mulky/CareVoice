"""Spoken teach-back: after the care card arrives, ask the patient when they should come
back to the hospital, score the answer against the template's red flags, re-explain the
ones they missed, and allow a fixed number of tries.

Tries add up: after a re-explanation the patient only needs to name the signs they missed.
Every scored try is a teachback.scored event; the discharge moves from sent to understood
or needs_followup (an alert or a closed episode is never overwritten).
"""

import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.registry import run_task
from app.ai.tasks.common import FlagSpec
from app.ai.tasks.score_teachback.schema import ScoreTeachbackInput, TeachBack
from app.core.config import Settings
from app.core.errors import AppError, not_found
from app.core.events import MESSAGE_SENT, TEACHBACK_SCORED, DomainEvent, EventBus
from app.core.models import (
    Discharge,
    DischargeStatus,
    Event,
    Message,
    MessageDirection,
    MessageKind,
    Patient,
    Template,
    TemplateTranslation,
)
from app.core.patient_access import PatientAccess
from app.modules.teachback.schemas import (
    FlagItem,
    Outcome,
    TeachbackAnswer,
    TeachbackResult,
    TeachbackState,
)
from app.providers.registry import ProviderRegistry
from app.rules.teachback import passes

PHRASES_FILE = Path(__file__).with_name("phrases.yaml")
FINAL = (Outcome.understood, Outcome.needs_followup)
# Teach-back only moves a discharge that is waiting for it; alerts and closed episodes stay.
MOVABLE = (DischargeStatus.sent,)


@lru_cache
def phrases() -> dict[str, dict[str, str]]:
    data: dict[str, dict[str, str]] = yaml.safe_load(PHRASES_FILE.read_text("utf-8"))
    return data


def phrase(lang: str, key: str, **values: Any) -> str:
    table = phrases().get(lang) or phrases()["en"]
    return str(table.get(key) or phrases()["en"][key]).format(**values)


def _sentence(text: str) -> str:
    text = text.strip()
    return text if not text or text[-1] in ".!?।" else f"{text}."


class Episode:
    """The discharge, its patient, and the red flags in the language the patient sees."""

    def __init__(self, session: Session, discharge_id: uuid.UUID) -> None:
        discharge = session.get(Discharge, discharge_id)
        if discharge is None:
            raise not_found("Discharge")
        patient = session.get(Patient, discharge.patient_id)
        template = session.get(Template, (discharge.template_id, discharge.template_version))
        assert patient is not None and template is not None
        wanted = patient.preferred_language
        translation = session.get(TemplateTranslation, (template.id, template.version, wanted))
        self.discharge = discharge
        self.patient = patient
        # Same rule as the care card: no verified translation -> English throughout.
        self.lang = wanted if (translation or wanted == "en") else "en"
        native = {
            f["id"]: f["label"]
            for f in (translation.content if translation else {}).get("red_flags", [])
        }
        self.flags = [FlagSpec.model_validate(f) for f in template.red_flags]
        self.labels = {f.id: native.get(f.id, f.label_en) for f in self.flags}
        self.labels_en = {f.id: f.label_en for f in self.flags}

    def items(self, ids: list[str]) -> list[FlagItem]:
        return [FlagItem(id=i, label=self.labels[i]) for i in ids if i in self.labels]


def _flag_list(labels: dict[str, str], ids: list[str], lang: str) -> str:
    return phrase(lang, "joiner").join(_sentence(labels[i]) for i in ids)


def reply_for(outcome: Outcome, missed: list[str], labels: dict[str, str], lang: str) -> str:
    flags = _flag_list(labels, missed, lang)
    if outcome is Outcome.understood:
        return phrase(lang, "also_remember", flags=flags) if missed else phrase(lang, "well_done")
    if outcome is Outcome.try_again:
        return f"{phrase(lang, 'reexplain', flags=flags)} {phrase(lang, 'ask_again')}"
    return phrase(lang, "follow_up", flags=flags)


def _post(
    session: Session,
    discharge: Discharge,
    direction: MessageDirection,
    kind: MessageKind,
    native: str,
    english: str | None,
    lang: str,
) -> Message:
    message = Message(
        hospital_id=discharge.hospital_id,
        discharge_id=discharge.id,
        direction=direction,
        kind=kind,
        text_native=native,
        text_en=english,
        language=lang,
    )
    session.add(message)
    session.flush()
    return message


# --- Asking the question ------------------------------------------------------------------


def ask_question(session: Session, bus: EventBus, discharge_id: uuid.UUID) -> Message:
    """Post the teach-back question to the chat, in the patient's language."""
    episode = Episode(session, discharge_id)
    discharge = episode.discharge
    message = _post(
        session,
        discharge,
        MessageDirection.to_patient,
        MessageKind.teachback_q,
        phrase(episode.lang, "question"),
        phrase("en", "question"),
        episode.lang,
    )
    bus.publish(
        session,
        DomainEvent(
            type=MESSAGE_SENT,
            hospital_id=discharge.hospital_id,
            discharge_id=discharge.id,
            payload={
                "message_id": str(message.id),
                "kind": message.kind.value,
                "language": episode.lang,
            },
        ),
    )
    return message


# --- State ----------------------------------------------------------------------------------


def _scored(session: Session, discharge_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Event.payload)
        .where(Event.discharge_id == discharge_id, Event.type == TEACHBACK_SCORED)
        .order_by(Event.created_at, Event.id)
    )
    return [dict(p) for p in rows]


def _result(episode: Episode, payload: dict[str, Any], settings: Settings) -> TeachbackResult:
    outcome = Outcome(payload["outcome"])
    missed = list(payload["missed_flag_ids"])
    return TeachbackResult(
        try_number=int(payload["try"]),
        max_tries=settings.teachback_max_tries,
        outcome=outcome,
        passed=bool(payload["passed"]),
        mentioned=episode.items(list(payload["mentioned_flag_ids"])),
        missed=episode.items(missed),
        reply=reply_for(outcome, missed, episode.labels, episode.lang),
        discharge_status=episode.discharge.status,
    )


def state(session: Session, settings: Settings, access: PatientAccess) -> TeachbackState:
    episode = Episode(session, access.discharge_id)
    tries = _scored(session, access.discharge_id)
    last = _result(episode, tries[-1], settings) if tries else None
    status = episode.discharge.status
    # Seeded episodes may be understood without any scored tries.
    complete = (last is not None and last.outcome in FINAL) or (
        not tries and status in (DischargeStatus.understood, DischargeStatus.needs_followup)
    )
    return TeachbackState(
        language=episode.lang,
        question=phrase(episode.lang, "question"),
        complete=complete,
        tries_used=len(tries),
        max_tries=settings.teachback_max_tries,
        discharge_status=status,
        last=last,
    )


# --- Scoring an answer ------------------------------------------------------------------------


async def answer(
    session: Session,
    bus: EventBus,
    providers: ProviderRegistry,
    settings: Settings,
    access: PatientAccess,
    body: TeachbackAnswer,
) -> TeachbackResult:
    current = state(session, settings, access)
    if current.complete:
        raise AppError(409, "teachback_complete", "Teach-back is already finished.")
    episode = Episode(session, access.discharge_id)
    discharge = episode.discharge
    lang = body.language or episode.patient.preferred_language
    try_number = current.tries_used + 1

    translated = await providers.translator.translate(body.transcript, lang, "en")
    answer_en = translated if translated and translated != body.transcript else None
    scored = await run_task(
        providers,
        "score_teachback",
        ScoreTeachbackInput(
            answer_native=body.transcript,
            answer_en=answer_en,
            language=lang,
            red_flags=episode.flags,
            pass_threshold=settings.teachback_pass_threshold,
        ),
    )
    result: TeachBack = scored.output

    # Tries add up: a sign named on an earlier try still counts.
    earlier = {f.id for f in current.last.mentioned} if current.last else set()
    named = earlier | set(result.mentioned_flag_ids)
    order = [f.id for f in episode.flags]
    mentioned = [i for i in order if i in named]
    missed = [i for i in order if i not in named]
    passed = passes(len(mentioned), len(order), settings.teachback_pass_threshold)

    if passed:
        outcome = Outcome.understood
    elif try_number >= settings.teachback_max_tries:
        outcome = Outcome.needs_followup
    else:
        outcome = Outcome.try_again

    answer_msg = _post(
        session,
        discharge,
        MessageDirection.to_doctor,
        MessageKind.teachback_a,
        body.transcript,
        answer_en,
        lang,
    )
    reply = reply_for(outcome, missed, episode.labels, episode.lang)
    reply_msg = _post(
        session,
        discharge,
        MessageDirection.to_patient,
        MessageKind.teachback_q,
        reply,
        reply_for(outcome, missed, episode.labels_en, "en"),
        episode.lang,
    )

    previous_status = discharge.status
    if outcome in FINAL and discharge.status in MOVABLE:
        discharge.status = DischargeStatus(outcome.value)
        session.flush()

    bus.publish(
        session,
        DomainEvent(
            type=TEACHBACK_SCORED,
            hospital_id=discharge.hospital_id,
            discharge_id=discharge.id,
            actor_type=access.recipient_type,
            actor_id=access.recipient_id,
            payload={
                "try": try_number,
                "outcome": outcome.value,
                "passed": passed,
                "mentioned_this_try": result.mentioned_flag_ids,
                "mentioned_flag_ids": mentioned,
                "missed_flag_ids": missed,
                "language": lang,
                "stt_confidence": body.stt_confidence,
                "source": scored.source.value,
                "needs_review": scored.needs_review,
                "answer_message_id": str(answer_msg.id),
                "reply_message_id": str(reply_msg.id),
                "status_before": previous_status.value,
                "status_after": discharge.status.value,
            },
        ),
    )
    return TeachbackResult(
        try_number=try_number,
        max_tries=settings.teachback_max_tries,
        outcome=outcome,
        passed=passed,
        mentioned=episode.items(mentioned),
        missed=episode.items(missed),
        reply=reply,
        discharge_status=discharge.status,
    )
