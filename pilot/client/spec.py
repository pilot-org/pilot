import dataclasses
import functools
import asyncclick as click
from omegaconf import (MISSING)
from typing import (Type, Optional, Tuple, List, Set, Dict, Any)

from pilot import conf as pconf
from . import connector as pconn
from . import core as pcore


# TODO:
# Fix omegaconf problems
# 1. can't get dataclass from dict
# 2. dataclass attr can't be class object
@dataclasses.dataclass(frozen=True)
class ConnectSetting:
    connect_type_path: Type[pconn.ConnectBase] = MISSING
    port: int = MISSING
    args: List[Any] = dataclasses.field(default_factory=list)
    kwargs: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def get_connect_info(self, *, host, username,
                         password) -> pconn.RemoteConnectInfo:
        connect_id = f'{username}@{host}:{self.port}'
        return pconn.RemoteConnectInfo(id=connect_id,
                                       host=host,
                                       username=username,
                                       port=self.port,
                                       password=password)

    @property
    def connect_type(self):
        module, name = self.connect_type_path.rsplit(',')
        return pconf._import(module, name)

    @classmethod
    def from_dict(cls, ori):
        data = dict(ori)
        return cls(**data)


@dataclasses.dataclass(frozen=True)
class ClientSpec:
    client_type_path: str = MISSING
    connect_settings: List[ConnectSetting] = dataclasses.field(
        default_factory=list)

    @property
    def client_type(self):
        module, name = self.client_type_path.rsplit(',')
        return pconf._import(module, name)

    @classmethod
    def from_dict(cls, ori):
        data = dict(ori)
        data['connect_settings'] = [
            ConnectSetting.from_dict(setting)
            for setting in data['connect_settings']
        ]
        return cls(**data)


@dataclasses.dataclass(frozen=True)
class ClientInfo:
    spec: ClientSpec = ClientSpec()
    host: str = MISSING
    username: str = MISSING
    password: Optional[str] = None

    @property
    def connect_types(self) -> Set[pconn.ConnectBase]:
        return self.connect_infos.keys()

    def get_connect_info(
        self, connect_cls: pconn.ConnectBase
    ) -> Tuple[pconn.RemoteConnection, List[Any], Dict[str, Any]]:
        setting = self._connect_setting_map.get(connect_cls)
        if setting is None:
            raise click.UsageError(
                f'{connect_cls} is not in spec: {self.spec.connect_settings}')
        return setting.get_connect_info(
            host=self.host, username=self.username,
            password=self.password), setting.args, setting.kwargs

    @functools.cached_property
    def _connect_setting_map(self) -> Dict[pconn.ConnectBase, ConnectSetting]:
        return {
            setting.connect_type: setting
            for setting in self.spec.connect_settings
        }

    @classmethod
    def from_dict(cls, ori):
        data = dict(ori)
        data['spec'] = ClientSpec.from_dict(data['spec'])
        return cls(**data)
