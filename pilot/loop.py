import functools
import contextlib
import anyio
from typing import (
    TypeVar, )

Func = TypeVar('Func')


async def gather(*coros):
    results = [None] * len(coros)

    async def run_and_store_result(pos):
        results[pos] = await coros[pos]

    async with anyio.create_task_group() as tg:
        for i in range(len(coros)):
            tg.start_soon(run_and_store_result, i)

    return tuple(results)


class TaskGroup:
    def __init__(self, origin) -> None:
        self._origin = origin

    async def __aenter__(self):
        return self._origin.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self._origin.__aexit(exc_type, exc_val, exc_tb)

    def start_soon(self, *args, **kwargs):
        return self._origin.start_soon(*args, **kwargs)

    async def start(self, raw_func, *args, **kwargs):
        @functools.wraps(raw_func)
        async def func(*, task_status):
            return await raw_func(*args, task_status=task_status, **kwargs)

        return await self._origin.start(func)

    def start_task(self, func: Func, *args, **kwargs):
        res = None

        async def notify(event):
            nonlocal res
            res = await func(*args, **kwargs)
            event.set()

        event = anyio.Event()
        self.start_soon(notify, event)

        async def wait():
            await event.wait()
            return res

        new_func = functools.update_wrapper(wait, func)
        future = new_func()
        return future


@contextlib.asynccontextmanager
async def create_task_group() -> TaskGroup:
    async with anyio.create_task_group() as tg:
        yield TaskGroup(tg)
