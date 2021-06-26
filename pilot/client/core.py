import os
import contextlib
import async_property
import tempfile
import asyncclick as click

from . import connector as pconn
from . import obj as pobj


class Client(pobj.ObjOwner):
    def __init__(self, client_info, *, connector, pool, name=None):
        self._client_info = client_info
        self._name = name or client_info.host
        self._connector = connector
        self._pool = pool

    def __repr__(self):
        return f'<{self.__class__.__name__} {self._name}>'

    def __eq__(self, other):
        return self._client_info == other._client_info

    @property
    def connector(self):
        return self._connector

    async def connect(self, connect_cls, sub_id=None):
        connect_info, args, kwargs = self._client_info.get_connect_info(
            connect_cls)
        return await self._connector.general_connect(connect_cls,
                                                     connect_info,
                                                     *args,
                                                     sub_id=sub_id,
                                                     **kwargs)

    async def close_all(self):
        self._connector.close_all()


class ShellClient(Client):
    @async_property.async_cached_property
    async def shell(self):
        return await self.connect(self._shell_cls)

    async def close_all(self):
        if self.__class__.shell.has_cache_value(self):
            del self.shell
        await super().close_all()

    async def run(self, *args, **kwargs):
        shell = await self.shell
        return await shell.run(*args, **kwargs)

    @staticmethod
    async def scp(source, destination, **kwargs):
        async def t(target):
            if isinstance(target, tuple):
                target = (await target[0].shell, target[1])
            return target

        return await pconn.scp(await t(source), await t(destination), **kwargs)

    @contextlib.asynccontextmanager
    async def use_file(self, file, write_mode=False):
        tmp_path = tempfile.mktemp(suffix='ssstool_open_')
        await self.scp((self, file), tmp_path)
        yield tmp_path
        if write_mode is True:
            await self.scp(tmp_path, (self, file))
        os.remove(tmp_path)

    @contextlib.asynccontextmanager
    async def open(self, file, mode, *args, **kwargs):
        async with self.use_file(file, write_mode='w' in mode) as fpath:
            with open(fpath, mode, *args, **kwargs) as f:
                yield f


class SubprocessClient(ShellClient):
    _shell_cls = pconn.Subprocess

    async def reboot(self):
        raise click.UsageError(
            'localhost cannot reboot. Otherwise process will be killed')


class AsyncsshClient(ShellClient):
    _shell_cls = pconn.Asyncssh

    async def reboot(self, **kwargs):
        res = await self._reboot(**kwargs)
        await self.close_all()
        return res

    async def _reboot(self):
        return self.run('reboot')


class ClientCachedPool(contextlib.AsyncExitStack):
    def __init__(self, client_info_map):
        super().__init__()
        self._clients = client_info_map

    @async_property.async_cached_property
    async def connector_pool(self):
        return await self.enter_async_context(pconn.ConnectorCachedPool())

    def get_client_info(self, client_id):
        if client_id == 'localhost':
            return pconn.local_info
        client_info = self._clients.get(client_id)
        if client_info is None:
            raise click.UsageError(f'Not find client: {client_id}')
        return client_info

    async def get_client(self, client_id):
        client_info = self.get_client_info(client_id)
        name = client_id
        client_type = client_info.spec.client_type
        connector_pool = await self.connector_pool
        connector = await connector_pool.get(client_id)
        return client_type(client_info,
                           connector=connector,
                           pool=self,
                           name=name)

    async def get_client_obj_getter(
        self,
        client,
        checker=None,
    ):
        client = await self.get_client(client)
        return pobj.ClientObjGetter(client=client, checker=checker)
