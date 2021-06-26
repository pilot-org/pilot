import contextlib
from typing import (Type, TypeVar, Optional, Union, Any)

from . import info as pinfo
from . import connection as pconn

C = TypeVar('C', pconn.Connection)


class Connector(contextlib.AsyncExitStack):
    def __init__(self):
        ...

    async def connect(self, *args, **kwargs) -> C:
        ...

    async def general_connect(self,
                              connect_cls: Type[C],
                              *args,
                              sub_id: Optional[str],
                              input_fit_local_connect_interface: bool = ...,
                              **kwargs) -> C:
        ...

    async def close_all(self) -> None:
        ...


class ConnectorCachedPool(contextlib.AsyncExitStack):
    def __init__(self) -> None:
        ...

    async def get(self, identify: Any) -> Connector:
        ...


async def scp(source: Union[str, tuple[pconn.Connection, str]],
              destination: Union[str, tuple[pconn.Connection,
                                            str]], **kwargs) -> None:
    ...
