import dataclasses
from typing import (NamedTuple)


@dataclasses.dataclass(frozen=True)
class ConnectInfo:
    id: str


@dataclasses.dataclass(frozen=True)
class RemoteConnectInfo(ConnectInfo):
    host: str
    username: str
    port: int
    password: str = None

    def __repr__(self):
        host = self.host
        username = self.username
        port = self.port
        return f'<{self.__class__.__name__} {username}@{host}:{port}>'


class TunnelInfo(NamedTuple):
    connect_info: ConnectInfo
    conn_type: str


_local_info = ConnectInfo(id='localhost')
