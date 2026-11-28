import uuid
from pathlib import Path

import pytest

from app.channels.base import (
    Channel,
    DeliveryResult,
    DeliveryState,
    OutboundMessage,
    RecipientType,
)
from app.channels.in_app import InAppChannel
from app.channels.registry import ChannelRegistry
from tests.support import make_settings

pytestmark = pytest.mark.anyio


def message(text: str = "ನಮಸ್ಕಾರ") -> OutboundMessage:
    return OutboundMessage(
        message_id=uuid.uuid4(),
        discharge_id=uuid.uuid4(),
        recipient_type=RecipientType.patient,
        recipient_id=uuid.uuid4(),
        language="kn",
        text=text,
    )


async def test_in_app_channel_sends() -> None:
    channel = InAppChannel()
    msg = message()
    result = await channel.send(msg)
    assert result.state is DeliveryState.sent
    assert result.external_id == str(msg.message_id)
    assert channel.delivered == [msg]


async def test_in_app_channel_rejects_empty_messages() -> None:
    result = await InAppChannel().send(message("   "))
    assert result.state is DeliveryState.failed


def test_in_app_satisfies_channel_interface() -> None:
    assert isinstance(InAppChannel(), Channel)


def test_default_channels_are_in_app_only(tmp_path: Path) -> None:
    registry = ChannelRegistry(make_settings(tmp_path))
    assert list(registry.channels) == ["in_app"]
    assert [s.model_dump() for s in registry.statuses()] == [
        {"name": "in_app", "status": "enabled"}
    ]


def test_planned_and_unknown_channels_are_reported_not_fatal(tmp_path: Path) -> None:
    registry = ChannelRegistry(make_settings(tmp_path, enabled_channels="in_app,whatsapp,pigeon"))
    assert list(registry.channels) == ["in_app"]
    assert {s.name: s.status for s in registry.statuses()} == {
        "in_app": "enabled",
        "whatsapp": "not_built",
        "pigeon": "unknown",
    }


def test_in_app_is_always_kept_so_patients_stay_reachable(tmp_path: Path) -> None:
    registry = ChannelRegistry(make_settings(tmp_path, enabled_channels="sms"))
    assert "in_app" in registry.channels


async def test_one_failing_channel_does_not_stop_the_others(tmp_path: Path) -> None:
    class Broken:
        name = "broken"

        async def send(self, message: OutboundMessage) -> DeliveryResult:
            raise ConnectionError("down")

    registry = ChannelRegistry(make_settings(tmp_path))
    registry.channels = {"broken": Broken(), "in_app": InAppChannel()}
    results = await registry.send_all(message())
    assert [(r.channel, r.state) for r in results] == [
        ("broken", DeliveryState.failed),
        ("in_app", DeliveryState.sent),
    ]
