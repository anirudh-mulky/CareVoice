"""In-app channel: the WhatsApp-style chat in the patient's browser.

The message row is already in the database, and the patient link reads it from there,
so sending only records that it was delivered to this recipient.
"""

from app.channels.base import DeliveryResult, DeliveryState, OutboundMessage


class InAppChannel:
    name = "in_app"

    def __init__(self) -> None:
        self.delivered: list[OutboundMessage] = []

    async def send(self, message: OutboundMessage) -> DeliveryResult:
        if not message.text.strip() and not message.audio_url:
            return DeliveryResult(self.name, DeliveryState.failed, "empty message")
        self.delivered.append(message)
        return DeliveryResult(self.name, DeliveryState.sent, external_id=str(message.message_id))
