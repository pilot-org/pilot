import async_property
from typing import (List, Dict)

from pilot.client import obj as pobj


def parser_ip_addr(raw_data: str, cmd: List[str]) -> Dict[str, Dict[str, str]]:
    ...


# the mixin only for the class inhert from pcore.ClientObj
class CachedInfoMixin(pobj.ClientObj):
    @async_property.async_cached_property
    async def raw_ip_addr(self) -> str:
        ...

    @async_property.async_cached_property
    async def ip_info(self) -> Dict[str, Dict[str, str]]:
        ...

    @async_property.async_cached_property
    async def pwd(self) -> str:
        ...
