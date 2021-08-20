import contextlib
import os
import asyncssh
import dataclasses
import asyncclick as click
from loguru import logger

from . import subprocess as pproc
from . import expect as pexp
from . import result as pres
from . import agent as pagent
from . import connection as pconn


class AsyncsshConnection(pconn.RemoteConnection):
    result_cls = pres.CmdRunResult

    def __init__(self, conn, **kwargs):
        super().__init__(**kwargs)
        self._conn = conn

    @property
    def origin(self):
        return self._conn

    async def _run(self, *argv, **kwargs):
        try:
            return await self._conn.run(*argv, **kwargs)
        except asyncssh.misc.ChannelOpenError as e:
            # TODO:
            pass

    @staticmethod
    async def scp(source, destination, **kwargs):
        def get_path(target):
            if not isinstance(target, tuple):
                target = (None, target)

            conn, path = target
            if isinstance(conn, AsyncsshConnection):
                return (conn.origin, path), f'{conn}:{path}'
            elif isinstance(conn, pproc.SubprocessConnection) or conn is None:
                return path, path
            raise pconn.UsageError(f'Not support {conn.__class__.__name__}')

        sinfo, sstr = get_path(source)
        dinfo, dstr = get_path(destination)
        logger.info(f'Start to scp {sstr} to {dstr}')
        await asyncssh.scp(sinfo, dinfo, **kwargs)
        logger.info(f'Success to scp {sstr} to {dstr}')


class AsyncsshAgent(pagent.ConnectRemoteAgent):
    connection_cls = AsyncsshConnection

    @classmethod
    @contextlib.asynccontextmanager
    async def _connect(cls, enter_info, **kwargs):
        connection_info = {
            'port': enter_info.port,
            'username': enter_info.username
        }
        ssh_kwargs = connection_info.copy()

        pwd = enter_info.password
        if pwd is not None:
            ssh_kwargs['password'] = pwd

        # TODO:
        # when connect fail, check reason and handle it.
        # case 1: the ip is not available
        # case 2: whthout authorized key
        try:
            async with asyncssh.connect(enter_info.host,
                                        known_hosts=None,
                                        **ssh_kwargs) as conn:
                connection_info['host'] = enter_info.host
                kwargs.update(connection_info)
                yield AsyncsshConnection(conn, **kwargs)
        except (OSError, ConnectionRefusedError) as e:
            raise click.UsageError(f'Failed to connect, due to {e}') from e


class AsyncsshRootAgent(AsyncsshAgent):
    pass_connector = True

    @classmethod
    @contextlib.asynccontextmanager
    async def _connect(cls, enter_info, connector, **kwargs):
        @contextlib.asynccontextmanager
        async def _connect(key_set):
            try:
                if enter_info.username != 'root':
                    logger.waring(
                        'Detected that username ({}) is not root on AsyncsshRootAgent, so changed to root',
                        enter_info.username)
                    root_enter_info = dataclasses.replace(enter_info,
                                                          username='root')
                else:
                    root_enter_info = enter_info
                conn = await connector.connect_by_agent(AsyncsshAgent,
                                                        info=root_enter_info,
                                                        **kwargs)
                yield conn
            except asyncssh.misc.PermissionDenied as e:
                if key_set is True:
                    raise asyncssh.misc.PermissionDenied(e.reason) from e

                logger.warning(
                    'Happened permission denied, so try to setup ssh key by expect. Then retry again'
                )

                local = await connector.connect(pproc.SubprocessAgent)

                tunnel = kwargs.get('tunnel', local)
                bridge_expect = await connector.connect(pexp.ExpectAgent,
                                                        enter_info,
                                                        tunnel=tunnel)

                res = await local.run('/bin/echo "$HOME"')
                home = res.stdout.strip()
                ssh_config_dir = os.path.join(home, '.ssh')

                res = await local.run(f'hostname')
                hostname = res.stdout.strip()

                ssh_pub_key_path = os.path.join(ssh_config_dir, 'id_rsa.pub')
                res = await local.run(f'/bin/cat {ssh_pub_key_path}')
                pub_key = res.stdout.strip()

                target_auth_dir = '/root/.ssh'
                target_auth_path = f'{target_auth_dir}/authorized_keys'
                await bridge_expect.run(
                    f'test -d {target_auth_dir} || mkdir {target_auth_dir}',
                    redirect_tty=True)
                await bridge_expect.run(
                    f'grep -q {hostname} {target_auth_path} 2>/dev/null || echo \'{pub_key}\' >> {target_auth_path}',
                    redirect_tty=True)
                logger.warning('{}\'s {} was setuped: {}', enter_info,
                               target_auth_path, pub_key)

                logger.warning('Retry to connect {} again', enter_info)
                async with _connect(True) as conn:
                    yield conn

        async with _connect(False) as conn:
            yield conn
