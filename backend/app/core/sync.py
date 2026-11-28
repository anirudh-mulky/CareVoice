"""Run a coroutine from synchronous code (event handlers run inside sync requests)."""

import asyncio
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

T = TypeVar("T")
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="carevoice-sync")


def run_sync(coro: Coroutine[Any, Any, T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)  # no loop in this thread: the common case
    # Called from inside a running loop: run it on a helper thread with its own loop.
    return _pool.submit(asyncio.run, coro).result()
