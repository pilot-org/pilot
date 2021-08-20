import os
import functools
import asyncclick as click
from loguru import logger


class _Cli(click.MultiCommand):
    _root_path = ''
    _root_module = ''
    _subpath = ''

    @classmethod
    def get_cli_module(cls):
        return cls._get_module(os.path.join(cls._subpath, 'cli.py'))

    @classmethod
    def _get_module(cls, subpath):
        import importlib

        def get_module_str(subpath):
            if subpath.endswith('.py'):
                subpath = subpath[:-3]
            return f"{cls._root_module}.{subpath.replace('/', '.')}"

        module_path = os.path.join(cls._root_path, subpath)
        import_module_str = get_module_str(subpath)
        logger.debug('Try to import {} by {}', import_module_str, module_path)
        try:
            return importlib.import_module(import_module_str)
        except ImportError as e:
            logger.error('Failed to import {}', subpath)
            raise click.UsageError(f'Failed to import {subpath}') from e

    @classmethod
    def enum_cmd_getter(cls, dir_subpath):
        dir_path = os.path.join(cls._root_path, dir_subpath)

        cmd_getter_map = {}
        for name in os.listdir(dir_path):
            path = os.path.join(name, dir_path, name)
            cmd_cli = os.path.isfile(path) and \
                name.endswith('.py') and \
                name.startswith('cmd_')
            grp_cli = os.path.isdir(path) and os.path.isfile(
                os.path.join(path, 'cli.py'))

            if cmd_cli or grp_cli:
                if cmd_cli:
                    cmd_name = name[4:-3]

                    def gen(p):
                        # Because path will be change at next loop
                        # So use function to copy string forcely
                        def getter():
                            subpath = os.path.relpath(p, cls._root_path)
                            module = cls._get_module(subpath)
                            return module.cli

                        return getter

                    cmd_getter_map[cmd_name] = gen(path)
                elif grp_cli:
                    cmd_name = name

                    def gen(n):
                        def getter():
                            subpath_for_new_cmd = os.path.join(dir_subpath, n)
                            logger.debug('Try to new command group cli for {}',
                                         subpath_for_new_cmd)
                            cli_cls = type(
                                f'{n}Cli', (_Cli, ), {
                                    '_getter': cls._getter,
                                    '_root_path': cls._root_path,
                                    '_root_module': cls._root_module,
                                    '_subpath': subpath_for_new_cmd
                                })
                            return cls._getter.get_cli(cli_cls)

                        return getter

                    cmd_getter_map[cmd_name] = gen(cmd_name)

        return cmd_getter_map

    @functools.cached_property
    def all_cmd_getter(self):
        return self.enum_cmd_getter(self._subpath)

    def list_commands(self, ctx):
        return self.all_cmd_getter.keys()

    def get_command(self, ctx, name):
        getter = self.all_cmd_getter[name]
        return getter()


_proj_path = os.path.dirname(os.path.dirname(__file__))


class FolderManageCliGetter:
    def __init__(self, root_path):
        self._real_path = os.path.realpath(root_path)
        self._root_module = os.path.relpath(self._real_path,
                                            _proj_path).replace('/', '.')
        self._root_cli = type(
            'RootCli', (_Cli, ), {
                '_getter': self,
                '_root_path': self._real_path,
                '_root_module': self._root_module
            })

    def get_root_cli(self):
        return self.get_cli(self.root_cli_cls)

    @property
    def root_cli_cls(self):
        return self._root_cli

    @functools.lru_cache
    def get_cli(self, cli_cls):
        grp_module = cli_cls.get_cli_module()
        grp_cli_getter = grp_module.cli_getter
        return grp_cli_getter(cli_cls)
