import contextlib
from abc import (ABC)
from typing import (Optional)

from . import info as pinfo
from . import connection as pconn
from . import connector as pconnector


class ConnectBase(ABC):
    enter_msg: str
    exit_msg: str
    pass_connector: bool

    @classmethod
    @contextlib.asynccontextmanager
    async def connect(cls,
                      connect_info: pinfo.ConnectInfo,
                      *args,
                      log: bool = ...,
                      connector: Optional[pconnector.Connector] = ...,
                      **kwargs):
        ...

    @classmethod
    @contextlib.asynccontextmanager
    async def _connect(cls, connect_info: pinfo.ConnectInfo, *args, **kwargs):
        ...

    @classmethod
    @contextlib.asynccontextmanager
    async def _handle_context_log(cls, connect_info: pinfo.ConnectInfo):
        ...


class ConnectLocalBase(ConnectBase):
    ...


class ConnectRemoteBase(ConnectBase):
    ...
