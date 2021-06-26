import abc
import io
import asyncclick as click
from loguru import logger

from . import result as pres


class Connection(metaclass=abc.ABCMeta):
    result_cls = pres.RunResult

    def __init__(self, parent_client=None):
        self._client = parent_client

    def __repr__(self):
        return self.__class__.__name__

    @staticmethod
    def _change_option(kwargs):
        redirect_tty = kwargs.pop('redirect_tty', None)
        redirect_stdout_tty = kwargs.pop('redirect_stdout_tty', None)
        redirect_stderr_tty = kwargs.pop('redirect_stderr_tty', None)
        if redirect_tty is True:
            kwargs['stdout'] = io.open(1, closefd=False)
            kwargs['stderr'] = io.open(2, closefd=False)
        else:
            if redirect_stdout_tty:
                kwargs['stdout'] = io.open(1, closefd=False)
            if redirect_stderr_tty:
                kwargs['stderr'] = io.open(2, closefd=False)

    async def run(self, *args, show_detail_opt=None, check=True, **kwargs):
        self._change_option(kwargs)
        result_cls = self.result_cls
        log_level = 'CMD_READ' if kwargs.pop('read_only', False) else 'CMD'

        logger.log(log_level, '{} run: <{}>', str(self), args)
        origin = await self._run(*args, **kwargs)
        result = result_cls(args, kwargs, origin, connection=self, check=check)
        await result.wait()

        result.show_detail(show_detail_opt)
        result.check_raise()

        return result

    @abc.abstractmethod
    async def _run(self, *argv, **kwargs):
        pass


class RemoteConnection(Connection):
    def __init__(self,
                 host=None,
                 username=None,
                 port=None,
                 password=None,
                 **kwargs):
        super().__init__(**kwargs)
        self._host = host
        self._username = username
        self._password = password
        self._port = port

    def __str__(self):
        return f'{self._username}@{self._host}:{self._port}'

    @property
    def host(self):
        return self._host

    @property
    def username(self):
        return self._username

    @property
    def port(self):
        return self._port

    # TODO: scp
