import abc

from typing import (Optional)

from . import interface as pit
from . import result as pres


class Connection(metaclass=abc.ABCMeta):
    def __init__(self, parent_client: pit.ClientInterface = None) -> None:
        ...

    async def run(self, *argv, show_detail_opt=None, **kwargs):
        ...

    @abc.abstractmethod
    async def _run(self, *argv, **kwargs) -> pres.RunResult:
        ...


class RemoteConnection(Connection, metaclass=abc.ABCMeta):
    def __init__(self,
                 host: str = None,
                 username: str = None,
                 port: Optional[int] = None,
                 password: str = None,
                 **kwargs):
        ...

    @property
    def host(self) -> str:
        ...

    @property
    def username(self) -> str:
        ...

    @property
    def port(self) -> int:
        ...
