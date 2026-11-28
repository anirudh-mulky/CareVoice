"""Channel registry: builds the channels named in ENABLED_CHANNELS."""

import logging
from collections.abc import Callable

from fastapi import Request
from pydantic import BaseModel

from app.channels.base import Channel, DeliveryResult, DeliveryState, OutboundMessage
from app.channels.in_app import InAppChannel
from app.core.config import Settings

logger = logging.getLogger("carevoice.channels")

AVAILABLE: dict[str, Callable[[Settings], Channel]] = {
    "in_app": lambda _settings: InAppChannel(),
}
PLANNED = {"whatsapp", "sms", "ivr"}


class ChannelStatus(BaseModel):
    name: str
    status: str  # "enabled" | "not_built" | "unknown"


class ChannelRegistry:
    def __init__(self, settings: Settings) -> None:
        self.channels: dict[str, Channel] = {}
        self._status: list[ChannelStatus] = []
        for name in settings.channel_names:
            factory = AVAILABLE.get(name)
            if factory is not None:
                self.channels[name] = factory(settings)
                self._status.append(ChannelStatus(name=name, status="enabled"))
            else:
                state = "not_built" if name in PLANNED else "unknown"
                logger.warning("channel %r is %s, skipping", name, state)
                self._status.append(ChannelStatus(name=name, status=state))
        if not self.channels:  # the patient must always be reachable in the app
            self.channels["in_app"] = InAppChannel()
            self._status.append(ChannelStatus(name="in_app", status="enabled"))

    def get(self, name: str) -> Channel | None:
        return self.channels.get(name)

    async def send_all(self, message: OutboundMessage) -> list[DeliveryResult]:
        """Send through every enabled channel; one failing channel never stops the others."""
        results: list[DeliveryResult] = []
        for name, channel in self.channels.items():
            try:
                results.append(await channel.send(message))
            except Exception as exc:  # noqa: BLE001 - report and continue
                logger.exception("channel %s failed", name)
                results.append(DeliveryResult(name, DeliveryState.failed, str(exc)))
        return results

    def statuses(self) -> list[ChannelStatus]:
        return list(self._status)


def get_channels(request: Request) -> ChannelRegistry:
    """FastAPI dependency."""
    registry: ChannelRegistry = request.app.state.channels
    return registry
