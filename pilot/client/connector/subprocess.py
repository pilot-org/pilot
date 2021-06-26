import asyncio
import contextlib

from . import core as pcore
from . import connection as pconn
from . import result as pres


class SubprocessRunResult(pres.CmdRunResult):
    result_cls = pres.CmdRunResult

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stdout = None
        self._stderr = None

    async def wait(self):
        self._stdout, self._stderr = tuple([
            std if std is None else std.decode('utf-8')
            for std in await self.origin.communicate()
        ])

    @property
    def stdout(self):
        return self._stdout

    @property
    def stderr(self):
        return self._stderr

    @property
    def exit_status(self):
        return self._origin.returncode


class SubprocessConnection(pconn.Connection):
    result_cls = SubprocessRunResult

    async def _run(self, *args, **kwargs):
        kwargs['stdout'] = kwargs.get('stdout', asyncio.subprocess.PIPE)
        kwargs['stderr'] = kwargs.get('stderr', asyncio.subprocess.PIPE)
        return await asyncio.create_subprocess_shell(*args, **kwargs)


class Subprocess(pcore.ConnectLocalBase):
    connection_cls = SubprocessConnection

    @contextlib.asynccontextmanager
    async def _connect(connect_info, **kwargs):
        yield SubprocessConnection(**kwargs)
