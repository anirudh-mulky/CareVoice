"""Who is acting. Round 2 has no login: staff pages run as the demo doctor
(role switcher labelled "demo"); production replaces this with session auth."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.models import Role, User


@dataclass(frozen=True)
class Staff:
    id: uuid.UUID
    hospital_id: uuid.UUID
    name: str
    role: Role


def current_doctor(session: Session) -> Staff:
    user = session.scalars(
        select(User).where(User.role == Role.doctor).order_by(User.created_at, User.name)
    ).first()
    if user is None:
        raise AppError(503, "no_staff", "No doctor is set up. Reset the demo data.")
    return Staff(user.id, user.hospital_id, user.name, user.role)
