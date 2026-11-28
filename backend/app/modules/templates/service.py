"""Templates: list the latest version of each, view any version, save a new version.

Versions are immutable: saving creates (id, version + 1), so a discharge that pinned an
older version keeps exactly the instructions the patient was given.
"""

import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import Staff
from app.core.errors import not_found
from app.core.models import Template, TemplateTranslation
from app.modules.templates.schemas import TemplateBody, TemplateOut, TemplateSave, TemplateSummary


def _languages(session: Session, hospital_id: uuid.UUID) -> dict[tuple[uuid.UUID, int], list[str]]:
    rows = session.execute(
        select(
            TemplateTranslation.template_id,
            TemplateTranslation.version,
            TemplateTranslation.language,
        ).where(TemplateTranslation.hospital_id == hospital_id)
    ).all()
    out: dict[tuple[uuid.UUID, int], list[str]] = defaultdict(lambda: ["en"])
    for tid, version, lang in rows:
        out[(tid, version)].append(lang)
    return out


def _latest(session: Session, hospital_id: uuid.UUID) -> list[Template]:
    latest = (
        select(Template.id, func.max(Template.version).label("version"))
        .where(Template.hospital_id == hospital_id)
        .group_by(Template.id)
        .subquery()
    )
    return list(
        session.scalars(
            select(Template)
            .join(latest, (Template.id == latest.c.id) & (Template.version == latest.c.version))
            .order_by(Template.name)
        )
    )


def list_templates(session: Session, staff: Staff) -> list[TemplateSummary]:
    langs = _languages(session, staff.hospital_id)
    return [
        TemplateSummary(
            id=t.id,
            version=t.version,
            name=t.name,
            condition=t.condition,
            medicines=len(t.medicines),
            red_flags=len(t.red_flags),
            minor_symptoms=len(t.minor_symptoms),
            languages=sorted(langs[(t.id, t.version)]),
            created_at=t.created_at,
        )
        for t in _latest(session, staff.hospital_id)
    ]


def get_template(
    session: Session, staff: Staff, template_id: uuid.UUID, version: int | None = None
) -> TemplateOut:
    versions = list(
        session.scalars(
            select(Template.version)
            .where(Template.id == template_id, Template.hospital_id == staff.hospital_id)
            .order_by(Template.version)
        )
    )
    if not versions or (version is not None and version not in versions):
        raise not_found("Template")
    tpl = session.get(Template, (template_id, version or versions[-1]))
    assert tpl is not None
    translations = {
        tr.language: tr.content
        for tr in session.scalars(
            select(TemplateTranslation).where(
                TemplateTranslation.template_id == tpl.id,
                TemplateTranslation.version == tpl.version,
            )
        )
    }
    return TemplateOut(
        id=tpl.id,
        version=tpl.version,
        versions=versions,
        name=tpl.name,
        condition=tpl.condition,
        medicines=tpl.medicines,
        dos=tpl.dos,
        donts=tpl.donts,
        red_flags=tpl.red_flags,
        minor_symptoms=tpl.minor_symptoms,
        reminders=tpl.reminders,
        follow_up_day=tpl.follow_up_day,
        languages=sorted(["en", *translations]),
        translations=translations,
        created_at=tpl.created_at,
    )


def save_template(session: Session, staff: Staff, body: TemplateSave) -> TemplateOut:
    template_id = body.id or uuid.uuid4()
    version = 1
    if body.id is not None:
        current = session.scalar(
            select(func.max(Template.version)).where(
                Template.id == body.id, Template.hospital_id == staff.hospital_id
            )
        )
        if current is None:
            raise not_found("Template")
        version = current + 1
    data = TemplateBody.model_validate(body.model_dump()).model_dump()
    session.add(
        Template(
            id=template_id,
            version=version,
            hospital_id=staff.hospital_id,
            doctor_id=staff.id,
            **data,
        )
    )
    session.flush()
    return get_template(session, staff, template_id, version)
