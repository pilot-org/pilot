from __future__ import annotations
import contextlib
import asyncio
from loguru import logger
from typing import (
    Generic,
    Optional,
    Type,
    TypeVar,
    overload,
    Union,
    Any,
    TYPE_CHECKING,
)

from . import info as pinfo
if TYPE_CHECKING:
    from . import agent as pagent

Agent = TypeVar('Agent', bound='pagent.ConnectAgent')
EnterInfo = TypeVar('EnterInfo', bound=pinfo.EnterInfo)
ConnectInfo = pinfo.ConnectInfo
SubID = TypeVar('SubID', str, int)


class Connector(contextlib.AsyncExitStack):
    def __init__(self) -> None:
        super().__init__()
        self._cached = {}

    @overload
    async def connect_by_agent(self,
                               agent: Type[Agent],
                               *args,
                               info: EnterInfo,
                               conn_id: Optional[str] = ...,
                               sub_id: Optional[SubID] = ...,
                               **kwargs):
        ...

    @overload
    async def connect_by_agent(self,
                               agent: Type[Agent],
                               *args,
                               info: ConnectInfo,
                               sub_id: Optional[SubID] = ...,
                               **kwargs):
        ...

    async def connect_by_agent(self,
                               agent: Type[Agent],
                               *args,
                               info=None,
                               conn_id=None,
                               sub_id=None,
                               **kwargs):
        from . import agent as pagent

        if issubclass(agent, pagent.ConnectLocalAgent):

            if info is None:
                info = pinfo._local_enter_info
            else:
                raise TypeError(
                    ' connect_by_agent() got an unexpected keyword argument \'info\''
                )
        elif not issubclass(agent, pagent.ConnectAgent):
            raise TypeError(f'Unknown {agent} ({type(agent)})')

        if isinstance(info, pinfo.EnterInfo):
            conn_info = pinfo.ConnectInfo(force_id=conn_id,
                                          sub_id=sub_id,
                                          enter_info=info)
        elif isinstance(info, pinfo.ConnectInfo):
            if conn_id is not None or sub_id is not None:
                raise TypeError(
                    f'Cannot supply conn_id({conn_id}) or sub_id({sub_id}) when info is ConnectInfo type'
                )
            conn_info = info
        else:
            raise TypeError(f'Unknown {info} ({type(info)})')

        if conn_info not in self._cached:
            if not issubclass(agent, pagent.ConnectLocalAgent):
                args = list(args)
                args.insert(0, conn_info.enter_info)
            cm = agent.connect(*args, connector=self, **kwargs)
            self._cached[conn_info] = await self.enter_async_context(cm)
        return self._cached[conn_info]

    async def close_all(self):
        await self.aclose()
        self._cached.clear()


_Connector = TypeVar('_Connector', bound=Connector)


class ConnectorCachedPool(contextlib.AsyncExitStack, Generic[_Connector]):
    local_info = pinfo._local_enter_info

    def __init__(self, connector_type: Type[_Connector] = Connector) -> None:
        super().__init__()
        self._connector_type = connector_type
        self._cached = {}

    async def get(self, identify: Any, *args, **kwargs) -> _Connector:
        if identify not in self._cached:
            self._cached[identify] = await self.enter_async_context(
                self._connector_type(*args, **kwargs))
        return self._cached[identify]

    async def get_lazy(self, connect_info):
        pass
        # TODO LazyConnection


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
