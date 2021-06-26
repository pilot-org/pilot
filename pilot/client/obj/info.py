import dataclasses
import re
import async_property
from loguru import logger
from typing import (Dict)

from pilot import conf as pconf
from . import info_core as pinfo
from . import core as pcore


class CachedInfoMixin:
    @async_property.async_cached_property
    async def raw_ip_addr(self):
        res = await self.client.run('/sbin/ip addr', redirect_stderr_tty=True)
        return res.stdout

    async def ip_info_getter(self):
        raw_data = await self.raw_ip_addr
        ip_interface_dict: Dict[str, Dict[str, str]] = {}
        pattern = r''
        pattern += '[0-9]+: (?P<name>[a-z0-9]+): .*\n'
        pattern += '[ \t]*link/[a-z]+ (?P<mac>[a-zA-Z0-9:]+) .*\n'
        pattern += '[ \t]*inet (?P<ip>[0-9.]+)/(?P<mask>[0-9]+) .*'
        for one in re.finditer(pattern, raw_data, re.MULTILINE):
            data = one.groupdict()
            key = data.pop('name')
            data['mask'] = int(data['mask'])
            ip_interface_dict[key] = data

        return ip_interface_dict

    def ip_addr_deleter(self):
        del self.raw_ip_addr

    ip_info = async_property.async_cached_property(ip_info_getter,
                                                   _fdel=ip_addr_deleter)

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


'''
class CachedInfoUtil:
    @pinfo.cached_info(depend_on_id=False)
    async def _get_by(self, cmd):
        res = await self.client.run(cmd, redirect_stderr_tty=True)
        return res.stdout


@dataclasses.dataclass
class _IpInfo:
    name: str
    ip: str
    mac: str
    mask: int


class NetworkInfo(CachedInfoUtil):
    @pinfo.cached_info_property
    async def ip_info_enum(self) -> Dict[str, _IpInfo]:
        raw = await self._get_by('/sbin/ip addr')
        ip_interface_dict: Dict[str, Dict[str, str]] = {}
        pattern = r''
        pattern += '[0-9]+: (?P<name>[a-z0-9]+): .*\n'
        pattern += '[ \t]*link/[a-z]+ (?P<mac>[a-zA-Z0-9:]+) .*\n'
        pattern += '[ \t]*inet (?P<ip>[0-9.]+)/(?P<mask>[0-9]+) .*'
        for one in re.finditer(pattern, raw, re.MULTILINE):
            data = one.groupdict()
            ip_interface_dict[data['name']] = pconf.dataclass_from_dict(
                _IpInfo, data)

        return ip_interface_dict
'''