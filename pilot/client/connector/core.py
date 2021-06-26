import contextlib
import asyncclick as click
from abc import (ABC, abstractmethod)
from loguru import logger

from . import level as plevel
from . import info as pinfo
from pilot import utils


class ConnectBase(ABC):
    enter_msg, exit_msg = ('exter', 'exit')
    pass_connector = False

    @classmethod
    @contextlib.asynccontextmanager
    async def connect(cls,
                      connect_info,
                      *args,
                      log=True,
                      connector=None,
                      **kwargs):
        if cls.pass_connector is True:
            if connector is None:
                raise click.UsageError(
                    f'{cls.__name__} wants to use connector, but it is not passed'
                )
            kwargs['connector'] = connector

        cm = cls._handle_context_log(
            connect_info) if log is True else contextlib.nullcontext()
        with cm:
            async with cls._connect(connect_info, *args, **kwargs) as conn:
                yield conn

    @classmethod
    @abstractmethod
    def _connect(cls, connect_info, *args, **kwargs):
        pass

    @classmethod
    @contextlib.contextmanager
    def _handle_context_log(cls, connect_info):
        entered = False
        name = cls.__name__

        def callback_when_exit(exc_type, exc_value, tb):
            if exc_type is not None:
                logger.warning(
                    'Failed to {} {} by {}, due to {}',
                    'do some operation on' if entered else cls.enter_msg,
                    connect_info, name, exc_value)
                if exc_type == TypeError:
                    logger.error(
                        f'Please check interface of _connect in {name}')

        logger.log(plevel.CONNECTION, 'Start to {} {} by {}', cls.enter_msg,
                   connect_info, name)
        with utils.call_when_exit(callback_when_exit):
            logger.log(plevel.CONNECTION, 'Success to {} {} by {}',
                       cls.enter_msg, connect_info, name)
            entered = True
            yield
            logger.log(plevel.CONNECTION, 'Success to {} {} by {}',
                       cls.exit_msg, connect_info, name)
        logger.log(plevel.CONNECTION, 'Close {}', connect_info)


class ConnectLocalBase(ConnectBase):
    @classmethod
    @contextlib.asynccontextmanager
    async def connect(cls, *args, **kwargs):
        async with super().connect(pinfo._local_info, *args, **kwargs) as conn:
            yield conn


class ConnectRemoteBase(ConnectBase):
    enter_msg, exit_msg = ('login', 'logout')
