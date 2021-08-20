import dataclasses
import re
import io
import async_property
import anyio
import asyncio
from loguru import logger
from typing import (Dict)

from pilot import conf as pconf
from . import obj as pobj


class CachedInfoUtil(pobj.CachedInfoGroupEntry):
    @pobj.cached_info(depend_on_id=False)
    async def get_by_cmd(self, cmd: str) -> str:
        res = await self.owner.run(cmd,
                                   redirect_stderr_tty=True,
                                   read_only=True)
        return res.stdout

    @pobj.cached_info(depend_on_id=False)
    async def watch(self,
                    watched_cmd: str,
                    post_cmd: str,
                    *,
                    event: anyio.Event,
                    interval: float = 0.1):
        async def watch(buf, msg):
            cmd = f'''first="true"; \
echo "{msg}";
while [ true ]; do \
    ctx="$({watched_cmd})"; \
    ctx="${{ctx//$'\n'/_}}"; \
    if [[ "$first" != "true" ]] && [[ "$ctx" != "$ctxLast" ]]; then \
        echo "finish";
        {post_cmd}; \
        break; \
    fi; \
    first="false"; \
    ctxLast="$ctx"; \
    sleep {interval}; \
done \
            '''
            await self.owner.run(cmd, stdout=buf, redirect_stderr_tty=True)

        async def notify_ready(buf, msg):
            while True:
                out = buf.getvalue()
                if out.startswith(msg):
                    event.set()
                    break
                await asyncio.sleep(0.1)

        with io.StringIO() as buf:
            msg = 'start to watch'
            tasks = [
                watch(buf, msg),
                notify_ready(buf, msg),
            ]
            await asyncio.gather(*tasks)


class CachedInfoMixin:
    @async_property.async_cached_property
    async def raw_sysctl_a(self):
        res = await self.client.run('/sbin/sysctl -a',
                                    redirect_stderr_tty=True)
        return res.stdout

    async def sysctl_a_getter(self) -> Dict[str, str]:
        raw_data = await self.raw_sysctl_a
        pattern = r'(?P<key>\S+) = (?P<value>\S+)'
        return {
            match.group('key'): match.group('value')
            for match in re.finditer(pattern, raw_data)
        }

    def sysctl_a_deleter(self):
        del self.raw_sysctl_a

    sysctl_a = async_property.async_cached_property(sysctl_a_getter,
                                                    _fdel=sysctl_a_deleter)


@dataclasses.dataclass
class _IpInfo:
    name: str
    ip: str
    mac: str
    mask: int


class NetworkInfo(pobj.CachedInfoGroupEntry):
    _util = CachedInfoUtil.as_property()

    @pobj.cached_info_property
    async def ip_info_enum(self) -> Dict[str, _IpInfo]:
        raw = await self._util.get_by_cmd('/sbin/ip addr')
        ip_interface_dict: Dict[str, _IpInfo] = {}
        pattern = r''
        pattern += '[0-9]+: (?P<name>[a-z0-9]+): .*\n'
        pattern += '[ \t]*link/[a-z]+ (?P<mac>[a-zA-Z0-9:]+) .*\n'
        pattern += '[ \t]*inet (?P<ip>[0-9.]+)/(?P<mask>[0-9]+) .*'
        for one in re.finditer(pattern, raw, re.MULTILINE):
            data = one.groupdict()
            ip_interface_dict[data['name']] = pconf.dataclass_from_dict(
                _IpInfo, data)

        return ip_interface_dict
