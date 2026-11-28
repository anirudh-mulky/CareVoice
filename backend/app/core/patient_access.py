"""Patient and carer links (no login). Shared by every module with patient-facing endpoints.

A link is /p/<token>; the token is 128 random bits, URL-safe. Only its SHA-256 hash is
stored. Tokens expire 30 days after the follow-up day and can be revoked.
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.models import AccessToken, ActorType, Discharge, Template

LINK_PREFIX = "/p/"
GRACE_DAYS = 30


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def expiry_for(session: Session, discharge: Discharge) -> datetime:
    template = session.get(Template, (discharge.template_id, discharge.template_version))
    follow_up = (template.follow_up_day if template else None) or 14
    end = discharge.discharged_on + timedelta(days=follow_up + GRACE_DAYS)
    return datetime.combine(end, time.max, tzinfo=UTC)


def issue_token(
    session: Session, discharge: Discharge, recipient_type: ActorType, recipient_id: uuid.UUID
) -> str:
    """Create a new link token and return it. The plain token is never stored."""
    token = secrets.token_urlsafe(16)  # 128 bits
    session.add(
        AccessToken(
            hospital_id=discharge.hospital_id,
            discharge_id=discharge.id,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            token_hash=_hash(token),
            expires_at=expiry_for(session, discharge),
        )
    )
    session.flush()
    return token


@dataclass(frozen=True)
class PatientAccess:
    discharge_id: uuid.UUID
    hospital_id: uuid.UUID
    recipient_type: ActorType  # patient or carer
    recipient_id: uuid.UUID


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def resolve_token(session: Session, token: str) -> PatientAccess:
    """The discharge a link belongs to, or a 404 that the patient UI shows kindly."""
    row = None
    if 10 <= len(token) <= 64:
        row = session.scalar(select(AccessToken).where(AccessToken.token_hash == _hash(token)))
    if row is None or row.revoked_at is not None or _aware(row.expires_at) < datetime.now(UTC):
        raise AppError(404, "link_invalid", "This link is not valid any more.")
    return PatientAccess(row.discharge_id, row.hospital_id, row.recipient_type, row.recipient_id)


def revoke_tokens(session: Session, discharge_id: uuid.UUID) -> int:
    """Revoke every link for a care episode (e.g. when the doctor closes it)."""
    result = session.execute(
        update(AccessToken)
        .where(AccessToken.discharge_id == discharge_id, AccessToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    return int(getattr(result, "rowcount", 0) or 0)


def link_path(token: str) -> str:
    return f"{LINK_PREFIX}{token}"
