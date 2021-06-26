import functools
import os
import json
import contextlib
import async_property

root_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


def get_proj_path():
    here_folder = os.path.abspath(os.path.dirname(__file__))
    proj_folder = os.path.dirname(here_folder)
    return proj_folder


class Git:
    def __init__(self, conn, proj_path):
        self._conn = conn
        self._path = proj_path

    @property
    def project_name(self):
        return os.path.basename(self._path)

    async def run(self, cmd, **kwargs):
        return await self._conn.run(self.get_cmd(cmd), **kwargs)

    def get_cmd(self, cmd):
        return f'/usr/bin/git -C {self._path} {cmd}'

    @async_property.async_cached_property
    async def cur_branch(self):
        return await self.__get_cur_branch()

    async def __get_cur_branch(self):
        reuslt = await self.run('branch | grep "*"')
        return reuslt.stdout[2:].rstrip()


class call_when_exit(contextlib.AbstractContextManager):
    def __init__(self, callback):
        self._callback = callback

    def __exit__(self, exc_type, exc_value, tb):
        self._callback(exc_type, exc_value, tb)


def wrap_parser_to_get(cmd_template, parser_func, check_func_name=True):
    if check_func_name and not parser_func.__name__.startswith('parser_'):
        raise NameError(
            f'Function<{parser_func.__name__}> name must start with parser_ if it is argument of warp_parser_to_get'
        )

    @functools.wraps(parser_func)
    async def getter(conn, *args, **kwargs):
        cmd = cmd_template.format(**kwargs)
        res = await conn.run(cmd, redirect_stderr_tty=True)
        return parser_func(res.stdout, cmd)

    return getter


get_json = wrap_parser_to_get('cat {path} | jq -c .',
                              json.loads,
                              check_func_name=False)

from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import Terminal256Formatter
from pprint import pformat


def pprint_color(obj):
    print(highlight(pformat(obj), PythonLexer(), Terminal256Formatter()))