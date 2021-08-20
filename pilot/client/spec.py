from __future__ import annotations
import contextlib
import dataclasses
import functools
import asyncclick as click
from loguru import logger
from typing import (
    TYPE_CHECKING,
    Callable,
    Generic,
    KeysView,
    Type,
    TypeVar,
    Optional,
    Tuple,
    List,
    Dict,
    Any,
    overload,
)

from asyncclick.exceptions import UsageError

from pilot import conf as pconf
from . import connector as pconn
if TYPE_CHECKING:
    from . import core as pcore

Agent = TypeVar('Agent', bound=pconn.ConnectAgent)
Client = TypeVar('Client', bound='pcore.Client')
EnterInfo = TypeVar('EnterInfo', bound=pconn.EnterInfo)
Connector = TypeVar('Connector', bound=pconn.Connector)


# TODO:
# Fix omegaconf problems
# 1. can't get dataclass from dict
# 2. dataclass attr can't be class object
@dataclasses.dataclass(frozen=True)
class ConnectSetting(Generic[Agent]):
    name: str
    force_connect_agent: Optional[Type[Agent]] = None
    connect_type_path: Optional[str] = None
    username: Optional[str] = None
    port: Optional[int] = None
    args: Tuple[Any, ...] = dataclasses.field(default_factory=tuple)
    kwargs: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.force_connect_agent is None and self.connect_type_path is None:
            raise click.UsageError(
                'Must supply force_connect_agent or connect_type_path')

    @property
    def connect_agent(self) -> Type[Agent]:
        if self.force_connect_agent is not None:
            return self.force_connect_agent
        if self.connect_type_path is None:
            raise click.UsageError(
                'Must supply force_connect_agent or connect_type_path')
        module, name = self.connect_type_path.rsplit(',')
        return pconf._import(module, name)

    @property
    def required_enter_info_type(self):
        self.connect_agent.required_enter_info_type


class LazyEnterInfo(pconf.LazyTypeByArgs, Generic[EnterInfo]):
    enter_info_checker_infos: List[Tuple[Callable[[Any], bool],
                                         EnterInfo]] = []

    @classmethod
    def register_enter_info(cls, checker: Callable[[Any], bool],
                            expected_type: EnterInfo):
        cls.enter_info_checker_infos.insert(0, (
            checker,
            expected_type,
        ))

    @classmethod
    def get_type(cls, *args, **kwargs):
        for checker, expected_type in cls.enter_info_checker_infos:
            if checker(*args, **kwargs) is True:
                return expected_type

        raise TypeError(
            f'Cannot get type by args={args}, kwargs={kwargs} from {cls.enter_info_checker_infos}'
        )


def _is_use_enter_info(*args, **kwargs) -> bool:
    return len(kwargs) == 0


LazyEnterInfo.register_enter_info(_is_use_enter_info, pconn.EnterInfo)


def _is_use_ssh_login_info(*args, **kwargs) -> bool:
    keys = kwargs.keys()
    if 'host' not in keys:
        return False
    if 'username' not in keys:
        return False
    expected_key_num = 4
    if 'port' not in keys:
        expected_key_num -= 1
    if 'password' not in keys:
        expected_key_num -= 1
    return len(keys) == expected_key_num


LazyEnterInfo.register_enter_info(_is_use_ssh_login_info, pconn.LoginSSHInfo)


@dataclasses.dataclass(frozen=True)
class ClientSpec(Generic[Client, EnterInfo]):
    force_client_type: Optional[Type[Client]] = None
    client_type_path: Optional[str] = None
    connect_settings: List[ConnectSetting] = dataclasses.field(
        default_factory=list)
    enter_info: Optional[EnterInfo] = None
    lazy_enter_info: Optional[LazyEnterInfo[EnterInfo]] = None

    def __post_init__(self) -> None:
        if self.force_client_type is None and self.client_type_path is None:
            raise click.UsageError(
                'Must supply force_client_type or client_type_path')
        if self.enter_info is not None and self.lazy_enter_info is not None:
            raise click.UsageError(
                'Cannot supply enter_info and lazy_enter_info simultaneously')

    @classmethod
    def from_dict(cls, info_dict):
        return pconf.dataclass_from_dict(cls, info_dict)

    @property
    def client_type(self) -> Type[Client]:
        if self.force_client_type is not None:
            return self.force_client_type
        if self.client_type_path is None:
            raise click.UsageError(
                'Must supply force_client_type or client_type_path')
        module, name = self.client_type_path.rsplit(',')
        return pconf._import(module, name)

    @functools.cached_property
    def _connect_setting_map(self) -> Dict[str, ConnectSetting]:
        return {setting.name: setting for setting in self.connect_settings}

    @property
    def connect_names(self) -> KeysView[Type[str]]:
        return self._connect_setting_map.keys()

    @overload
    def get_connect_setting(self, connect_name: str) -> ConnectSetting[Agent]:
        ...

    @overload
    def get_connect_setting(self, agent: Type[Agent]) -> ConnectSetting[Agent]:
        ...

    def get_connect_setting(self, conn):
        if isinstance(conn, str):
            setting: Optional[
                ConnectSetting[Agent]] = self._connect_setting_map.get(conn)
            if setting is None:
                raise click.UsageError(
                    f'{conn} is not in spec: {self.connect_settings}')
            return setting
        elif issubclass(conn, pconn.ConnectAgent):
            setting: Optional[ConnectSetting[Agent]] = None
            for s in self.connect_settings:
                if s.connect_agent == conn:
                    return s
            raise click.UsageError(
                f'Cannot find agent {conn} in connect settings.')
        else:
            raise TypeError(f'Unknown conn: {conn} ({type(conn)})')

    @overload
    def get_enter_info(
        self,
        connect_name: str,
    ) -> Tuple[EnterInfo, List[Any], Dict[str, Any]]:
        ...

    @overload
    def get_enter_info(
            self,
            agent: Type[Agent]) -> Tuple[EnterInfo, List[Any], Dict[str, Any]]:
        ...

    @overload
    def get_enter_info(
        self, conn_setting: ConnectSetting[Agent]
    ) -> Tuple[EnterInfo, List[Any], Dict[str, Any]]:
        ...

    def get_enter_info(self, conn):
        setting = conn if isinstance(
            conn, ConnectSetting) else self.get_connect_setting(conn)
        if self.enter_info is None:
            if self.lazy_enter_info is None:
                enter_info = pconn.EnterInfo()
            else:
                enter_info = self.lazy_enter_info.value
        else:
            enter_info = self.enter_info
        if setting.port is not None:
            enter_info = dataclasses.replace(enter_info, port=setting.port)
        if setting.username is not None:
            enter_info = dataclasses.replace(enter_info,
                                             username=setting.username)

        return enter_info, setting.args, setting.kwargs

    @overload
    @contextlib.asynccontextmanager
    async def connect(self, conn_type: Type[Agent]):
        ...

    @overload
    @contextlib.asynccontextmanager
    async def connect(self, connect_name: str):
        ...

    @contextlib.asynccontextmanager
    async def connect(self, conn):
        setting = self.get_connect_setting(conn)
        enter_info, args, kwargs = self.get_enter_info(setting)
        async with setting.connect_agent.connect(enter_info, *args,
                                                 **kwargs) as c:
            yield c

    def gen_client(self, *args, name: str, connector: Connector, **kwargs):
        client_type = self.client_type
        return client_type(spec=self,
                           *args,
                           connector=connector,
                           name=name,
                           **kwargs)
