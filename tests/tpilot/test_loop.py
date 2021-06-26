import pytest
import asyncio
import anyio
from loguru import logger

from pilot import loop as ploop


@pytest.mark.anyio
@pytest.mark.parametrize('anyio_backend', ['asyncio'])
async def test_event_loop_equal():
    async def async_do_something():
        await anyio.sleep(1)
        return 1

    def do_something():
        return 1
        #return anyio.run(async_do_something())

    async def do():
        return do_something()

    assert await ploop.gather(do(), do()) == (1, 1)


async def do_something(id, time, ret=None):
    logger.info('{} start', id)
    await asyncio.sleep(time)
    logger.info('{} end', id)
    return ret


@pytest.mark.asyncio
@pytest.mark.urulogs('tests.tpilot.test_loop')
async def test_asyncio_create_task(urulogs):

    loop = asyncio.get_event_loop()
    future1 = loop.create_task(do_something(1, 1))
    future2 = loop.create_task(do_something(2, 1))
    await future1
    await future2
    assert urulogs.output == [
        'INFO:tests.tpilot.test_loop:1 start',
        'INFO:tests.tpilot.test_loop:2 start',
        'INFO:tests.tpilot.test_loop:1 end',
        'INFO:tests.tpilot.test_loop:2 end',
    ]


@pytest.mark.asyncio
@pytest.mark.urulogs('tests.tpilot.test_loop')
async def test_tg_start_task(urulogs):
    async with ploop.create_task_group() as tg:
        future1 = tg.start_task(do_something, 1, 1, 1)
        future2 = tg.start_task(do_something, 2, 1, 2)
        logger.info('1 return {}', await future1)
        logger.info('2 return {}', await future2)
    assert urulogs.output == [
        'INFO:tests.tpilot.test_loop:1 start',
        'INFO:tests.tpilot.test_loop:2 start',
        'INFO:tests.tpilot.test_loop:1 end',
        'INFO:tests.tpilot.test_loop:2 end',
        'INFO:tests.tpilot.test_loop:1 return 1',
        'INFO:tests.tpilot.test_loop:2 return 2',
    ]
