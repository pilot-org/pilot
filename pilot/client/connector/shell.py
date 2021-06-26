import contextlib

from . import core as pcore
from . import subprocess as pproc
from . import asyncssh as pssh


class AutoShell(pcore.ConnectBase):
    @classmethod
    @contextlib.asynccontextmanager
    async def _connect(cls, connect_info):
        import ifcfg

        def is_local_ip(ip):
            for interface in ifcfg.interfaces().values():
                if ip in interface['inet4']:
                    return True
            return False

        if is_local_ip(connect_info.host):
            connect_cls = pproc.Subprocess
            args = ()
        else:
            connect_cls = pssh.AsyncsshRoot
            args = (connect_info)
        async with connect_cls.connect(*args) as conn:
            yield conn