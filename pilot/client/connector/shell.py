import contextlib

from . import agent as pagent
from . import subprocess as pproc
from . import asyncssh as pssh


class AutoShellAgent(pagent.ConnectAgent):
    @classmethod
    @contextlib.asynccontextmanager
    async def _connect(cls, enter_info):
        import ifcfg

        def is_local_ip(ip):
            for interface in ifcfg.interfaces().values():
                if ip in interface['inet4']:
                    return True
            return False

        if is_local_ip(enter_info.host):
            connect_cls = pproc.SubprocessAgent
            args = ()
        else:
            connect_cls = pssh.AsyncsshRootAgent
            args = enter_info
        async with connect_cls.connect(*args) as conn:
            yield conn