"""Send a chat message to the patient and every carer, on every enabled channel.

Used by modules that message the family after delivery (outcomes, reminders). The first
care card goes through delivery instead, because each recipient also gets their own link.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.channels.base import OutboundMessage, RecipientType
from app.channels.registry import ChannelRegistry
from app.core.models import Carer, Discharge, Message, Patient


async def send_to_family(
    session: Session, channels: ChannelRegistry, discharge: Discharge, message: Message
) -> list[dict[str, str]]:
    patient = session.get(Patient, discharge.patient_id)
    assert patient is not None
    carers = session.scalars(select(Carer).where(Carer.patient_id == patient.id))
    recipients = [(RecipientType.patient, patient.id, patient.phone)] + [
        (RecipientType.carer, c.id, c.phone) for c in carers
    ]
    results = []
    for recipient_type, recipient_id, phone in recipients:
        outbound = OutboundMessage(
            message_id=message.id,
            discharge_id=discharge.id,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            language=message.language,
            text=message.text_native or message.text_en or "",
            audio_url=message.audio_url,
            phone=phone,
        )
        for result in await channels.send_all(outbound):
            results.append(
                {
                    "recipient": recipient_type.value,
                    "channel": result.channel,
                    "state": result.state.value,
                }
            )
    return results
