import contextlib
import asyncio
from loguru import logger

from . import core as pcore
from . import info as pinfo


class Connector(contextlib.AsyncExitStack):
    def __init__(self):
        super().__init__()
        self._cached = {}

    async def connect(self, *args, **kwargs):
        return await self.general_connect(
            *args, input_fit_local_connect_interface=True, **kwargs)

    async def general_connect(self,
                              connect_cls,
                              *args,
                              sub_id=None,
                              input_fit_local_connect_interface=False,
                              **kwargs):
        if issubclass(connect_cls, pcore.ConnectLocalBase):
            connect_info = pinfo._local_info
            if input_fit_local_connect_interface is False:
                args = list(args)
                args.pop(0)
        else:
            connect_info = args[0]
        conn_id = (connect_cls, connect_info, sub_id)
        if conn_id not in self._cached:
            cm = connect_cls.connect(*args, connector=self, **kwargs)
            self._cached[conn_id] = await self.enter_async_context(cm)
        return self._cached[conn_id]

    async def close_all(self):
        await self.aclose()
        self._cached.clear()


class ConnectorCachedPool(contextlib.AsyncExitStack):
    local_info = pinfo._local_info

    def __init__(self):
        super().__init__()
        self._cached = {}

    async def get(self, identify):
        if identify not in self._cached:
            self._cached[identify] = await self.enter_async_context(
                Connector())
        return self._cached[identify]

    async def get_lazy(self, connect_info):
        pass
        # TODO LazyConnection


async def scp(source, destination, **kwargs):
    from . import asyncssh as pssh

    # TODO: handle special module in general module
    async def t(target):
        if isinstance(target, tuple):
            target = (await target[0].conn, target[1])
        return target

    source = await t(source)
    destination = await t(destination)
    return await pssh.AsyncsshConnection.scp(source, destination, **kwargs)


def retry(expection=Exception, retry_max=10, inteval=1):
    def wrap(raw_func, connect_info):
        async def func(*args, **kwargs):
            retry_count = 0
            while True:
                try:
                    async with raw_func(*args, **kwargs) as conn:
                        yield conn
                except expection as e:
                    logger.warning('Happened connection lost at {} of {}',
                                   retry_count, retry_max)
                    if retry_count == retry_max:
                        raise RuntimeError('Retry failed') from e
                    await asyncio.sleep(inteval)

        return func

    return wrap
