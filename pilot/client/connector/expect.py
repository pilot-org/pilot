import os
import contextlib
import asyncssh
import asyncclick as click

from . import core as pcore
from . import result as pres
from . import connection as pconn
from . import subprocess as pproc
from . import asyncssh as pssh
from pilot import utils

_remote_expect_path: str = '/tmp/auto-ssh.exp'
_local_expect_path: str = os.path.join(utils.root_dir, 'assh', 'auto-ssh.exp')


class ExpectConnection(pconn.Connection):
    result_cls = pres.CmdRunResult

    def __init__(self, connect_info, tunnel_conn: pconn.Connection, **kwargs):
        super().__init__(**kwargs)
        self._client_info = connect_info
        self._conn = tunnel_conn

    async def _run(self, *cmds, **kwargs):
        info = self._client_info
        cmd = ' '.join([f'"{c}"' for c in cmds])
        return await self._conn.run(
            f'/usr/bin/expect {_remote_expect_path} "{info.host}" "{info.username}" "{info.password}" "{info.port}" {cmd}',
            **kwargs)


async def _check_expect_supported(tunnel_conn: pconn.Connection) -> None:
    res = await tunnel_conn.run('which expect', check=False)
    if res.exit_status != 0:
        # TODO: add which host need to install expect
        raise click.UsageError(f'Please install expect first')


async def _check_expect_exist(tunnel_conn: pconn.Connection) -> bool:
    res = await tunnel_conn.run(f'test -f {_remote_expect_path}', check=False)
    return res.exit_status == 0


async def _prepare_expect_env(tunnel_conn: pconn.Connection) -> bool:
    if isinstance(tunnel_conn, pproc.SubprocessConnection):
        await tunnel_conn.run(
            f'/bin/cp {_local_expect_path} {_remote_expect_path}')
    elif isinstance(tunnel_conn, pssh.AsyncsshConnection):
        # TODO Fix SFTPConnectionLost error
        await asyncssh.scp(_local_expect_path,
                           (tunnel_conn.origin, _remote_expect_path))
    else:
        raise NotImplementedError
    return True


class Expect(pcore.ConnectBase):
    connection_cls = ExpectConnection

    @classmethod
    @contextlib.asynccontextmanager
    async def _connect(cls, connect_info, tunnel=None, **kwargs):
        if tunnel is None:
            raise AttributeError(f'Request tunnel to run expect')

        await _check_expect_supported(tunnel)
        if await _check_expect_exist(tunnel) == False:
            await _prepare_expect_env(tunnel)

        yield ExpectConnection(connect_info, tunnel, **kwargs)
