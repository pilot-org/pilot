from abc import (abstractmethod)
from typing import (Generic, TypeVar, Optional, List, Dict, Any)

from . import connection as pconn

T = TypeVar('T')


class ExitStatusNotSuccess(Exception):
    def __init__(self, msg: str, result: RunResult):
        ...

    @property
    def result(self) -> RunResult:
        ...


class RunResult(Generic[T]):
    def __init__(self,
                 args: List[Any],
                 kwargs: Dict[str, Any],
                 origin: T,
                 connection: Optional[pconn.Connection] = ...,
                 check: bool = ...):
        self._args: List[Any] = ...
        self._kwargs: Dict[str, Any] = ...
        self._origin: T = ...
        self._check: bool = ...
        self._connection: Optional[pconn.Connection] = ...
        ...

    @property
    def origin(self) -> T:
        ...

    @abstractmethod
    @property
    def exit_status(self):
        ...

    @abstractmethod
    @property
    def success(self) -> bool:
        ...

    @property
    def info(self):
        ...

    async def wait(self) -> None:
        ...

    def check_raise(self) -> None:
        ...

    def show_detail(self, option: Optional[str]) -> None:
        ...

    def _secho(self) -> None:
        ...


class CmdRunResult(RunResult):
    @property
    def command(self) -> str:
        ...

    @property
    def stdout(self) -> Optional[str]:
        ...

    @property
    def stderr(self) -> Optional[str]:
        ...

    @property
    def info(self) -> str:
        ...

    @property
    def exit_status(self) -> int:
        ...

    @property
    def success(self) -> bool:
        ...
