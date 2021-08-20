import dataclasses
from typing import (
    Generic,
    NamedTuple,
    Optional,
    TypeVar,
    Union,
)


@dataclasses.dataclass(frozen=True)
class EnterInfo:
    @property
    def info_str(self) -> str:
        return ''


_EnterInfo = TypeVar('_EnterInfo', bound=EnterInfo)


@dataclasses.dataclass(frozen=True)
class LoginInfo(EnterInfo):
    host: str

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} host={self.host}>'

    @property
    def info_str(self) -> str:
        return self.host


@dataclasses.dataclass(frozen=True)
class LoginSSHInfo(LoginInfo):
    username: str
    port: int = 22
    password: Optional[str] = None

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} {self.info_str}'

    @property
    def info_str(self) -> str:
        host = self.host
        username = self.username
        port = self.port
        return f'{username}@{host}:{port}'


@dataclasses.dataclass(frozen=True)
class ConnectInfo(Generic[_EnterInfo]):
    force_id: Optional[str] = None
    sub_id: Optional[Union[str, int]] = None
    enter_info: _EnterInfo = EnterInfo()

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} id={self.id} info={self.enter_info.info_str}>'

    def __hash__(self) -> int:
        return hash(self.id)

    @property
    def id(self):
        return self.enter_info.info_str if self.force_id is None else self.force_id


class TunnelInfo(NamedTuple):
    connect_info: ConnectInfo
    conn_type: str


_local_enter_info: EnterInfo = EnterInfo()
_local_conn_info: ConnectInfo[_EnterInfo] = ConnectInfo(
    force_id='localhost', enter_info=_local_enter_info)
