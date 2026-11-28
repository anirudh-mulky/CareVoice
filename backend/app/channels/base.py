"""Delivery channels (spec: "Delivery channels by name").

delivery sends every patient/carer message through each enabled channel. Round 2 has
in_app; whatsapp, sms and ivr are added later as new files, with no caller changes.
"""

import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable


class RecipientType(StrEnum):
    patient = "patient"
    carer = "carer"


class DeliveryState(StrEnum):
    sent = "sent"
    failed = "failed"


@dataclass(frozen=True)
class OutboundMessage:
    message_id: uuid.UUID
    discharge_id: uuid.UUID
    recipient_type: RecipientType
    recipient_id: uuid.UUID
    language: str
    text: str
    audio_url: str | None = None
    phone: str | None = None


@dataclass(frozen=True)
class DeliveryResult:
    channel: str
    state: DeliveryState
    detail: str = ""
    external_id: str | None = None


@runtime_checkable
class Channel(Protocol):
    name: str

    async def send(self, message: OutboundMessage) -> DeliveryResult: ...
