import contextlib
import dataclasses
import async_property
from typing import (TypeVar, Union, Optional, Dict, Any, Type)

from . import spec as pspec
from . import obj as pobj
from . import connector as pconn


class Client:
    def __init__(self, client_info: pspec.ClientInfo, *,
                 connector: pconn.Connector, pool: ClientCachedPool,
                 name: Optional[str]) -> None:
        ...

    @property
    def spec(self) -> pspec.ClientSpec:
        ...

    @property
    def connector(self) -> pconn.Connector:
        ...

    async def connect(self,
                      connect_cls: Type[pconn.ConnectBase],
                      sub_id=Optional[str]) -> pconn.Connection:
        ...

    async def close_all(self) -> None:
        ...


class ShellClient(Client):
    @async_property.async_cached_property
    async def shell(self) -> pconn.Connection:
        ...

    async def close_all(self) -> None:
        ...

    async def run(self, *args, **kwargs) -> pconn.RunResult:
        ...

    @staticmethod
    async def scp(source: Union[str, tuple[pconn.Connection, str]],
                  destination: Union[str, tuple[pconn.Connection,
                                                str]], **kwargs) -> None:
        ...

    @contextlib.asynccontextmanager
    async def use_file(self, file: str, write_mode: bool = ...) -> str:
        ...

    @contextlib.asynccontextmanager
    async def open(self, file: str, mode: str, *args, **kwargs):
        ...


class SubprocessClient(ShellClient):
    async def reboot(self):
        ...


class AsyncsshClient(ShellClient):
    async def reboot(self) -> pconn.RunResult:
        ...

    async def _reboot(self) -> pconn.RunResult:
        ...


class ClientCachedPool(contextlib.AsyncExitStack):
    def __init__(self, client_info_map: Dict[str, pspec.ClientInfo],
                 **kwargs) -> None:
        ...

    @async_property.async_cached_property
    async def connector_pool(self) -> pconn.ConnectorCachedPool:
        ...

    def get_client_info(self, client_id: str) -> pconn.ClientInfo:
        ...

    async def get_client(self, client_id: str) -> Client:
        ...

    async def get_client_obj_getter(
        self,
        client_id: str,
        checker=Optional[pobj.Checker],
    ) -> pobj.ClientObjGetter:
        ...
