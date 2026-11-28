import asyncio

import pytest

from app.core.sync import run_sync


async def double(x: int) -> int:
    await asyncio.sleep(0)
    return x * 2


def test_run_sync_without_a_loop() -> None:
    assert run_sync(double(2)) == 4


@pytest.mark.anyio
async def test_run_sync_inside_a_running_loop() -> None:
    assert run_sync(double(3)) == 6
