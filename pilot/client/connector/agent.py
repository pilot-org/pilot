import contextlib
from typing import (
    ClassVar,
    Generic,
    Optional,
    Type,
    TypeVar,
)
import asyncclick as click
from abc import (ABC, abstractmethod)
from loguru import logger

from . import level as plevel
from . import info as pinfo
from . import connector as pconn
from . import connection as pconnection
from pilot import utils

Conn = TypeVar('Conn', bound=pconnection.Connection)


class ConnectAgent(ABC, Generic[Conn]):
    enter_msg: str = 'enter'
    exit_msg: str = 'exit'
    pass_connector: bool = False
    required_enter_info_type: ClassVar[Type[pinfo.EnterInfo]]
    connection_cls: ClassVar[Conn]

    @classmethod
    @contextlib.asynccontextmanager
    async def connect(cls,
                      enter_info: pinfo._EnterInfo,
                      *args,
                      log: bool = True,
                      connector: Optional[pconn.Connector] = None,
                      **kwargs):
        if not hasattr(cls, 'required_enter_info_type'):
            raise NotImplementedError(
                f'\'required_enter_info_type\' is not implemented in {cls}.')

        if not isinstance(enter_info, cls.required_enter_info_type):
            raise TypeError(
                f'Enter_info must be {cls.required_enter_info_type} at least, but {type(enter_info)} was gotten'
            )
        if cls.pass_connector is True:
            if connector is None:
                raise click.UsageError(
                    f'{cls.__name__} wants to use connector, but it is not passed'
                )
            kwargs['connector'] = connector

        cm = cls._handle_context_log(
            enter_info) if log is True else contextlib.nullcontext()
        with cm:
            async with cls._connect(enter_info, *args, **kwargs) as conn:
                yield conn

    @classmethod
    @abstractmethod
    def _connect(cls, enter_info: pinfo._EnterInfo, *args, **kwargs):
        pass

    @classmethod
    @contextlib.contextmanager
    def _handle_context_log(cls, enter_info: pinfo._EnterInfo):
        entered = False
        name = cls.__name__

        def callback_when_exit(exc_type, exc_value, tb):
            if exc_type is not None and (exc_type == click.exceptions.Exit
                                         and exc_value.exit_code != 0):
                logger.warning(
                    'Failed to {} {} by {}, due to {}',
                    'do some operation on' if entered else cls.enter_msg,
                    enter_info, name, exc_value)
                if exc_type == TypeError:
                    logger.error(
                        f'Please check interface of _connect in {name}')

        logger.log(plevel.CONNECTION, 'Start to {} {} by {}', cls.enter_msg,
                   enter_info, name)
        with utils.call_when_exit(callback_when_exit):
            logger.log(plevel.CONNECTION, 'Success to {} {} by {}',
                       cls.enter_msg, enter_info, name)
            entered = True
            yield
            logger.log(plevel.CONNECTION, 'Success to {} {} by {}',
                       cls.exit_msg, enter_info, name)
        logger.log(plevel.CONNECTION, 'Close {}', enter_info)


class ConnectLocalAgent(ConnectAgent):
    required_enter_info_type = pinfo.EnterInfo

    @classmethod
    @contextlib.asynccontextmanager
    async def connect(cls, *args, **kwargs):
        async with super().connect(pinfo._local_enter_info, *args,
                                   **kwargs) as conn:
            yield conn


class ConnectRemoteAgent(ConnectAgent):
    enter_msg = 'login'
    exit_msg = 'logout'
    required_enter_info_type = pinfo.LoginInfo
