from __future__ import annotations
import os
import contextlib
import async_property
import tempfile
import asyncclick as click
from loguru import logger
from typing import (
    ClassVar,
    Generic,
    Optional,
    TypeVar,
    Union,
    Tuple,
    Dict,
    Type,
    overload,
    Final,
)

from . import spec as pspec
from . import connector as pconn
from . import obj as pobj

Agent = TypeVar('Agent', bound=pconn.ConnectAgent)
Spec = pspec.ClientSpec
Conn = TypeVar('Conn', bound=pconn.Connection)
SubID = TypeVar('SubID', str, int)


class _PerClientConnector(pconn.Connector):
    def __init__(self, spec: Spec):
        super().__init__()
        self._spec = spec

    @overload
    async def connect(self, conn_agent: Type[Agent],
                      sub_id: Optional[SubID]) -> Agent.connection_cls:
        ...

    @overload
    async def connect(self, connect_name: str,
                      sub_id: Optional[SubID]) -> Conn:
        ...

    async def connect(self, conn, sub_id):
        setting = self._spec.get_connect_setting(conn)
        agent = setting.connect_agent
        enter_info, args, kwargs = self._spec.get_enter_info(setting)
        return await self.connect_by_agent(
            agent,
            *args,
            info=None
            if issubclass(agent, pconn.ConnectLocalAgent) else enter_info,
            conn_id=setting.name,
            sub_id=sub_id,
            **kwargs)


class Client(pobj.ObjOwner):
    def __init__(self,
                 *,
                 spec: Spec,
                 connector: _PerClientConnector,
                 name: Optional[str] = None):
        super().__init__()
        self._spec = spec
        self._name = name or spec.enter_info.info_str
        self._connector = connector

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} {self._name}>'

    def __eq__(self, other) -> bool:
        return self._client_spec == other._client_spec

    @overload
    async def connect(self,
                      conn: Type[Agent],
                      sub_id: Optional[SubID] = ...) -> Agent.connection_cls:
        ...

    @overload
    async def connect(self, conn: str, sub_id: Optional[SubID] = None) -> Conn:
        ...

    async def connect(self, conn, sub_id=None):
        return await self._connector.connect(conn, sub_id)

    async def close_all(self) -> None:
        self._connector.close_all()


_Client = TypeVar('_Client', bound=Client)


class ShellClient(Client, Generic[Agent]):
    _shell_agent: ClassVar[Agent]

    @async_property.async_cached_property
    async def shell(self) -> Agent.connection_cls:
        return await self.connect(self._shell_agent)

    async def close_all(self) -> None:
        if self.__class__.shell.has_cache_value(self):
            del self.shell
        await super().close_all()

    async def run(self, *args, **kwargs) -> pconn.RunResult:
        shell = await self.shell
        return await shell.run(*args, **kwargs)

    @staticmethod
    async def scp(source: Union[str, Tuple[ShellClient, str]],
                  destination: Union[str, Tuple[ShellClient,
                                                str]], **kwargs) -> None:
        async def t(target):
            if isinstance(target, tuple):
                target = (await target[0].shell, target[1])
            return target

        return await pconn.scp(await t(source), await t(destination), **kwargs)

    @contextlib.asynccontextmanager
    async def use_file(self, file: str, write_mode: bool = False) -> str:
        tmp_path = tempfile.mktemp(suffix='ssstool_open_')
        await self.scp((self, file), tmp_path)
        yield tmp_path
        if write_mode is True:
            await self.scp(tmp_path, (self, file))
        os.remove(tmp_path)

    @contextlib.asynccontextmanager
    async def open(self, file: str, mode: str, *args, **kwargs):
        async with self.use_file(file, write_mode='w' in mode) as fpath:
            with open(fpath, mode, *args, **kwargs) as f:
                yield f


class SubprocessClient(ShellClient):
    _shell_agent: Final[Type[pconn.SubprocessAgent]] = pconn.SubprocessAgent

    async def reboot(self) -> pconn.RunResult:
        raise click.UsageError(
            'localhost cannot reboot. Otherwise process will be killed')


class AsyncsshClient(ShellClient):
    _shell_agent: ClassVar[Agent] = pconn.AsyncsshAgent

    async def reboot(self, **kwargs) -> pconn.RunResult:
        res = await self._reboot(**kwargs)
        await self.close_all()
        return res

    async def _reboot(self) -> pconn.RunResult:
        return await self.run('reboot')


class ClientCachedPool(contextlib.AsyncExitStack):
    @classmethod
    def from_dict(cls, infos):
        return cls({
            name: pspec.ClientSpec.from_dict(info)
            for name, info in infos.items()
        })

    def __init__(self, client_info_map: Dict[str, Spec]):
        super().__init__()
        self._client_specs: Dict[str, Spec] = client_info_map

    @async_property.async_cached_property
    async def connector_pool(
            self) -> pconn.ConnectorCachedPool[_PerClientConnector]:
        return await self.enter_async_context(
            pconn.ConnectorCachedPool(connector_type=_PerClientConnector))

    def get_client_spec(self, client_name) -> Spec:
        # TODO: fix localhost
        client_spec = self._client_specs.get(client_name)
        if client_spec is None:
            raise click.UsageError(f'Not find client by id: {client_name}')
        return client_spec

    async def get_client(self, client_name: str, *args, **kwargs) -> _Client:
        spec = self.get_client_spec(client_name)
        connector_pool = await self.connector_pool
        connector = await connector_pool.get(client_name, spec)
        return spec.gen_client(*args,
                               connector=connector,
                               name=client_name,
                               **kwargs)

    async def get_client_obj_getter(
        self,
        client,
        checker=None,
    ):
        client = await self.get_client_spec(client)
        return pobj.ClientObjGetter(client=client, checker=checker)


def get_localhost_spec_info(client_cls: Type[_Client] = SubprocessClient,
                            conn_name='localhost'):
    return pspec.ClientSpec(force_client_type=client_cls,
                            connect_settings=[
                                pspec.ConnectSetting(
                                    name=conn_name,
                                    force_connect_agent=pconn.SubprocessAgent)
                            ])
