"""Delivery: on discharge.approved, build the care card in the patient's language, post it
to the chat, issue patient and carer links, and send through every enabled channel.

The card's medical content always comes from the doctor's template and its verified
translation; only the doctor's short extra instructions are translated live, and those
are marked so the patient (and doctor) can see which lines were not verified.
"""

import logging
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.channels.base import OutboundMessage, RecipientType
from app.channels.registry import ChannelRegistry
from app.core.errors import AppError, not_found
from app.core.events import (
    MESSAGE_PLAYED,
    MESSAGE_SENT,
    PATIENT_LANGUAGE_CHANGED,
    DomainEvent,
    EventBus,
)
from app.core.models import (
    ActorType,
    Carer,
    Discharge,
    DischargeStatus,
    Hospital,
    Message,
    MessageDirection,
    MessageKind,
    Patient,
    Template,
    TemplateTranslation,
    utcnow,
)
from app.core.patient_access import PatientAccess, issue_token, link_path
from app.core.sync import run_sync
from app.modules.delivery.schemas import (
    CardLabels,
    CareCard,
    CareExtra,
    CareMedicine,
    ChatMessage,
    DemoPatientLink,
    HospitalInfo,
    PatientHome,
    PatientLink,
    Viewer,
)
from app.providers.registry import ProviderRegistry
from app.rules.lexicon import get_lexicon
from app.rules.text import normalise

logger = logging.getLogger("carevoice.delivery")
PHRASES_FILE = Path(__file__).with_name("card_phrases.yaml")


@lru_cache
def phrases() -> dict[str, dict[str, str]]:
    data: dict[str, dict[str, str]] = yaml.safe_load(PHRASES_FILE.read_text("utf-8"))
    return data


def phrase(lang: str, key: str, **values: Any) -> str:
    table = phrases().get(lang) or phrases()["en"]
    return str(table.get(key) or phrases()["en"][key]).format(**values)


def recovery_day(discharge: Discharge) -> int:
    return max(1, (utcnow().date() - discharge.discharged_on).days + 1)


def _sentence(text: str, lang: str) -> str:
    text = text.strip()
    if not text or text[-1] in ".!?।:":
        return text
    return text + phrase(lang, "full_stop")


def _english_medicine(m: dict[str, Any]) -> str:
    parts = [m.get("dose"), m.get("frequency")]
    if m.get("duration_days"):
        parts.append(f"{m['duration_days']} days")
    return ", ".join(str(p) for p in parts if p)


def build_card(
    session: Session,
    discharge: Discharge,
    name: str,
    wanted: str,
    translator_lookup: dict[str, str],
) -> CareCard:
    """The care card in `wanted` language (English if no verified translation)."""
    template = session.get(Template, (discharge.template_id, discharge.template_version))
    if template is None:
        raise not_found("Template")
    translation = session.get(TemplateTranslation, (template.id, template.version, wanted))
    lang = wanted if (translation or wanted == "en") else "en"
    content: dict[str, Any] = translation.content if translation else {}

    flag_labels = {f["id"]: f["label"] for f in content.get("red_flags", [])}
    red_flags = [flag_labels.get(f["id"], f["label_en"]) for f in template.red_flags]
    meds_native = {m["name"]: m["instructions"] for m in content.get("medicines", [])}
    medicines = [
        CareMedicine(
            name=m["name"], instructions=meds_native.get(m["name"]) or _english_medicine(m)
        )
        for m in template.medicines
    ]
    extras = [
        CareExtra(
            text=translator_lookup.get(e, e), translated=lang == "en" or e in translator_lookup
        )
        for e in discharge.extra_instructions
    ]
    follow_up = content.get("follow_up") or (
        phrase(lang, "follow_up", day=template.follow_up_day) if template.follow_up_day else None
    )
    title = content.get("name") or template.name
    return CareCard(
        language=lang,
        translated=translation is not None or wanted == "en",
        title=title,
        greeting=phrase(lang, "greeting", name=name, template=title),
        red_flags_title=content.get("red_flags_title") or phrase(lang, "red_flags_title"),
        red_flags=red_flags,
        medicines=medicines,
        dos=list(content.get("dos") or template.dos),
        donts=list(content.get("donts") or template.donts),
        extras=extras,
        follow_up=follow_up,
        labels=CardLabels(
            medicines=phrase(lang, "medicines"),
            do=phrase(lang, "do"),
            dont=phrase(lang, "dont"),
            extras=phrase(lang, "extras"),
        ),
    )


def spoken_text(card: CareCard) -> str:
    """The voice note: greeting, then red flags first, then everything else."""
    lang = card.language
    lines = [card.greeting, _sentence(card.red_flags_title, lang)]
    lines += [_sentence(f, lang) for f in card.red_flags]
    if card.medicines:
        lines.append(_sentence(card.labels.medicines, lang))
        lines += [_sentence(f"{m.name}: {m.instructions}", lang) for m in card.medicines]
    if card.dos:
        lines.append(_sentence(card.labels.do, lang))
        lines += [_sentence(d, lang) for d in card.dos]
    if card.donts:
        lines.append(_sentence(card.labels.dont, lang))
        lines += [_sentence(d, lang) for d in card.donts]
    if card.extras:
        lines.append(_sentence(card.labels.extras, lang))
        lines += [_sentence(e.text, lang) for e in card.extras]
    if card.follow_up:
        lines.append(_sentence(card.follow_up, lang))
    return " ".join(line for line in lines if line)


async def translate_extras(
    providers: ProviderRegistry, extras: list[str], lang: str
) -> dict[str, str]:
    """Live translation of the doctor's extras; only real translations are returned."""
    out: dict[str, str] = {}
    if lang == "en":
        return out
    for text in extras:
        translated = await providers.translator.translate(text, "en", lang)
        if translated and translated != text:
            out[text] = translated
    return out


def _load_episode(
    session: Session, discharge_id: uuid.UUID
) -> tuple[Discharge, Patient, list[Carer]]:
    discharge = session.get(Discharge, discharge_id)
    if discharge is None:
        raise not_found("Discharge")
    patient = session.get(Patient, discharge.patient_id)
    assert patient is not None
    carers = list(
        session.scalars(
            select(Carer).where(Carer.patient_id == patient.id).order_by(Carer.created_at)
        )
    )
    return discharge, patient, carers


def deliver(
    session: Session,
    bus: EventBus,
    providers: ProviderRegistry,
    channels: ChannelRegistry,
    discharge_id: uuid.UUID,
) -> Message:
    """Post the care card to the chat and send it to the patient and every carer."""
    discharge, patient, carers = _load_episode(session, discharge_id)
    lang = patient.preferred_language
    lookup = run_sync(translate_extras(providers, list(discharge.extra_instructions), lang))
    card = build_card(session, discharge, patient.name, lang, lookup)
    english = (
        card if card.language == "en" else build_card(session, discharge, patient.name, "en", {})
    )

    message = Message(
        hospital_id=discharge.hospital_id,
        discharge_id=discharge.id,
        direction=MessageDirection.to_patient,
        kind=MessageKind.instructions,
        text_native=spoken_text(card),
        text_en=spoken_text(english),
        language=card.language,
    )
    session.add(message)
    session.flush()

    recipients: list[tuple[RecipientType, uuid.UUID, str | None, ActorType]] = [
        (RecipientType.patient, patient.id, patient.phone, ActorType.patient)
    ] + [(RecipientType.carer, c.id, c.phone, ActorType.carer) for c in carers]

    results = []
    for recipient_type, recipient_id, phone, actor in recipients:
        token = issue_token(session, discharge, actor, recipient_id)
        outbound = OutboundMessage(
            message_id=message.id,
            discharge_id=discharge.id,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            language=card.language,
            text=f"{message.text_native}\n{link_path(token)}",
            phone=phone,
        )
        for result in run_sync(channels.send_all(outbound)):
            results.append(
                {
                    "recipient": recipient_type.value,
                    "channel": result.channel,
                    "state": result.state.value,
                }
            )
            if result.state.value != "sent":
                logger.warning(
                    "delivery to %s via %s failed: %s",
                    recipient_type,
                    result.channel,
                    result.detail,
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
                "language": card.language,
                "translated": card.translated,
                "deliveries": results,
            },
        ),
    )
    return message


# --- Patient-facing reads -------------------------------------------------------------


def _viewer(session: Session, access: PatientAccess, patient: Patient) -> Viewer:
    if access.recipient_type is ActorType.carer:
        carer = session.get(Carer, access.recipient_id)
        return Viewer(type=ActorType.carer, name=carer.name if carer else "Carer")
    return Viewer(type=ActorType.patient, name=patient.name)


def viewer_language(session: Session, access: PatientAccess, patient: Patient) -> str:
    """A carer can read in their own language; everyone else sees the patient's."""
    if access.recipient_type is ActorType.carer:
        carer = session.get(Carer, access.recipient_id)
        if carer is not None and carer.preferred_language:
            return carer.preferred_language
    return patient.preferred_language


async def patient_home(
    session: Session, providers: ProviderRegistry, access: PatientAccess
) -> PatientHome:
    discharge, patient, _ = _load_episode(session, access.discharge_id)
    hospital = session.get(Hospital, discharge.hospital_id)
    wanted = viewer_language(session, access, patient)
    lookup = await translate_extras(providers, list(discharge.extra_instructions), wanted)
    card = build_card(session, discharge, patient.name, wanted, lookup)
    return PatientHome(
        patient_name=patient.name,
        viewer=_viewer(session, access, patient),
        language=card.language,
        ui_language=wanted,
        hospital=HospitalInfo(
            name=hospital.name if hospital else "", phone=hospital.phone if hospital else None
        ),
        status=discharge.status,
        recovery_day=recovery_day(discharge),
        card=card,
    )


def chat(session: Session, access: PatientAccess) -> list[ChatMessage]:
    rows = session.scalars(
        select(Message)
        .where(Message.discharge_id == access.discharge_id)
        .order_by(Message.created_at, Message.id)
    )
    return [
        ChatMessage(
            id=m.id,
            direction=m.direction,
            kind=m.kind,
            text=m.text_native or m.text_en or "",
            text_en=m.text_en,
            language=m.language,
            audio_url=m.audio_url,
            played_at=m.played_at,
            created_at=m.created_at,
        )
        for m in rows
    ]


def mark_played(
    session: Session, bus: EventBus, access: PatientAccess, message_id: uuid.UUID
) -> None:
    message = session.get(Message, message_id)
    if message is None or message.discharge_id != access.discharge_id:
        raise not_found("Message")
    first = message.played_at is None
    if first:
        message.played_at = utcnow()
    bus.publish(
        session,
        DomainEvent(
            type=MESSAGE_PLAYED,
            hospital_id=access.hospital_id,
            discharge_id=access.discharge_id,
            actor_type=access.recipient_type,
            actor_id=access.recipient_id,
            payload={"message_id": str(message_id), "first_play": first},
        ),
    )


# --- Links for the doctor ---------------------------------------------------------------


def issue_links(
    session: Session, hospital_id: uuid.UUID, discharge_id: uuid.UUID
) -> list[PatientLink]:
    discharge, patient, carers = _load_episode(session, discharge_id)
    if discharge.hospital_id != hospital_id:
        raise not_found("Discharge")
    if discharge.status is DischargeStatus.draft:
        raise AppError(409, "not_sent", "Approve the discharge before sharing links.")
    links = [
        PatientLink(
            recipient_type=ActorType.patient,
            name=patient.name,
            language=patient.preferred_language,
            url=link_path(issue_token(session, discharge, ActorType.patient, patient.id)),
        )
    ]
    links += [
        PatientLink(
            recipient_type=ActorType.carer,
            name=c.name,
            relation=c.relation,
            language=c.preferred_language,
            url=link_path(issue_token(session, discharge, ActorType.carer, c.id)),
        )
        for c in carers
    ]
    return links


def demo_links(session: Session, hospital_id: uuid.UUID) -> list[DemoPatientLink]:
    """Demo only: a link for every sent discharge (latest per patient)."""
    rows = session.execute(
        select(Discharge, Patient, Template)
        .join(Patient, Patient.id == Discharge.patient_id)
        .join(
            Template,
            (Template.id == Discharge.template_id)
            & (Template.version == Discharge.template_version),
        )
        .where(Discharge.hospital_id == hospital_id, Discharge.status != DischargeStatus.draft)
        .order_by(Discharge.created_at.desc())
    ).all()
    seen: set[uuid.UUID] = set()
    out = []
    for discharge, patient, template in rows:
        if patient.id in seen:
            continue
        seen.add(patient.id)
        out.append(
            DemoPatientLink(
                patient_name=patient.name,
                template_name=template.name,
                language=patient.preferred_language,
                status=discharge.status,
                links=issue_links(session, hospital_id, discharge.id),
            )
        )
    return sorted(out, key=lambda d: d.patient_name)


def change_language(
    session: Session, bus: EventBus, access: PatientAccess, language: str | None, spoken: str | None
) -> str:
    """The patient (or carer) picks or says their language; their own preference changes."""
    lex = get_lexicon()
    code = language
    if code is None and spoken:
        names = lex.language_names()
        said = normalise(spoken).strip(" .!?")
        code = names.get(said) or next((c for n, c in names.items() if n in said.split()), None)
    if code not in lex.languages:
        raise AppError(422, "unknown_language", "Choose Kannada, Hindi, Tamil or English.")
    discharge, patient, _ = _load_episode(session, access.discharge_id)
    person: Patient | Carer | None = (
        session.get(Carer, access.recipient_id)
        if access.recipient_type is ActorType.carer
        else patient
    )
    assert person is not None
    before = person.preferred_language
    person.preferred_language = code
    session.flush()
    bus.publish(
        session,
        DomainEvent(
            type=PATIENT_LANGUAGE_CHANGED,
            hospital_id=access.hospital_id,
            discharge_id=access.discharge_id,
            actor_type=access.recipient_type,
            actor_id=access.recipient_id,
            payload={"from": before, "to": code, "by_voice": language is None},
        ),
    )
    return code
