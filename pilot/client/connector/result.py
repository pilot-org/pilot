import asyncclick as click
from loguru import logger
from abc import (ABC, abstractmethod)

from . import core as pconn


class ExitStatusNotSuccess(Exception):
    def __init__(self, msg, result):
        super().__init__(msg)
        self._result = result

    @property
    def result(self):
        return self._result


class RunResult(ABC):
    def __init__(self, args, kwargs, origin, connection=None, check=True):
        if origin is None:
            pconn.UsageError('Must pass result')
        self._args = args
        self._kwargs = kwargs
        self._origin = origin
        self._check = check
        self._connection = connection

    @property
    def origin(self):
        return self._origin

    @property
    @abstractmethod
    def exit_status(self):
        pass

    @property
    @abstractmethod
    def success(self) -> bool:
        pass

    @property
    def info(self):
        return self._args

    async def wait(self):
        pass

    def check_raise(self):
        if self._check is True and not self.success:
            raise ExitStatusNotSuccess(
                f'Exit status of <{self.info}> is {self.exit_status}', self)

    def show_detail(self, option):
        if option is None:
            return
        if option == 'secho':
            self._secho()
            return
        elif option == 'secho_when_error':
            if not self.success():
                self._secho()
                return

        logger.warning('Failed to exec <%s> with exit_status=%d and err=<%s>',
                       self.info, self.exit_status, self.stderr)

    def _secho(self):
        click.secho(
            f'Failed to execute command: <{self.info}> with exit_status={self.exit_status}',
            fg='red')
        if self.stdout:
            click.secho('stdout:', fg='red')
            click.secho(self.stdout)
        if self.stderr:
            click.secho('stderr:', fg='red')
            click.secho(self.stderr)


class CmdRunResult(RunResult):
    @property
    def command(self):
        return self._args[0]

    @property
    def stdout(self):
        return self._origin.stdout

    @property
    def stderr(self):
        return self._origin.stderr

    @property
    def info(self):
        return self.command

    @property
    def exit_status(self):
        return self._origin.exit_status

    @property
    def success(self):
        return self.exit_status == 0
