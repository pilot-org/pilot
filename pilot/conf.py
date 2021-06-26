import sys
import re
import enum
import dataclasses
import asyncclick as click
from traitlets.config import loader
from omegaconf import OmegaConf
from loguru import logger
from typing import (
    Union, )

from pilot import error as perr


class YAMLFileConfigLoader(loader.FileConfigLoader):
    @staticmethod
    def register_resolver(*args, **kwargs):
        OmegaConf.register_resolver(*args, **kwargs)

    @classmethod
    def load(cls, *args, **kwargs):
        loader = cls(*args, **kwargs)
        loader.load_config()
        return loader.config

    def load_config(self):
        self.clear()
        try:
            self._find_file()
        except IOError as e:
            raise loader.ConfigFileNotFound(str(e))
        dct = self._read_file_as_dict()
        self.config = self._convert_to_config(dct)
        return self.config

    def _read_file_as_dict(self):
        conf = OmegaConf.load(self.full_filename)
        return OmegaConf.to_container(conf, resolve=True)

    def _convert_to_config(self, dictionary):
        if 'version' in dictionary:
            version = dictionary.pop('version')
        else:
            version = 1

        if version == 1:
            return loader.Config(dictionary)
        else:
            raise ValueError(
                'Unknown version of YAML config file: {version}'.format(
                    version=version))


def _import(module_str, *attr_name_paths):
    import importlib

    name = attr_name_paths[0]
    try:
        module = importlib.__import__(module_str, fromlist=[name])
        m = module
        try:
            for n in attr_name_paths:
                m = getattr(m, n)
            return m
        except AttributeError as e:
            raise click.UsageError(f'"{m}" has no {n} attribute') from e
    except ImportError as e:
        raise click.UsageError(
            f'Failed to do "from {module_str} import {name}"') from e


YAMLFileConfigLoader.register_resolver('import', _import)


def dataclass_from_dict(klass,
                        dikt,
                        convert_by_type=True,
                        convert_failed_continue=True,
                        logger_exception=True):
    try:
        fieldtypes = {f.name: f.type for f in dataclasses.fields(klass)}
        return klass(
            **{
                fname: dataclass_from_dict(
                    ftype,
                    dikt[fname],
                    convert_by_type=convert_by_type,
                    convert_failed_continue=convert_failed_continue,
                    logger_exception=logger_exception)
                for fname, ftype in fieldtypes.items()
            })
    except TypeError:
        pass

    if convert_by_type is True:
        if klass == type(None):
            if dikt == None:
                return None
            raise TypeError('Type NoneType must be None')
        if klass == bool:
            if dikt in ('1', 1, True):
                return True
            elif isinstance(dikt, str) and dikt.lower() == 'true':
                return True
            elif isinstance(dikt, bytes) and dikt.lower() == b'true':
                return True
            elif dikt in ('0', 0, False):
                return False
            elif isinstance(dikt, str) and dikt.lower() == 'false':
                return False
            elif isinstance(dikt, bytes) and dikt.lower() == b'false':
                return False
            raise TypeError(
                f'Failed to convert {dikt}(type: {type(dikt)}) to bool type')

        if issubclass(klass, enum.Enum):
            for _, member in klass.__members__.items():
                if dikt == member.value:
                    return member

        if hasattr(klass, '__origin__'):
            if klass.__origin__ == list:
                return list(
                    [dataclass_from_dict(klass.__args__[0], i) for i in dikt])
            elif klass.__origin__ == Union:
                for type_arg in reversed(klass.__args__):
                    try:
                        return dataclass_from_dict(
                            type_arg,
                            dikt,
                            convert_by_type=convert_by_type,
                            convert_failed_continue=False,
                            logger_exception=False)
                    except TypeError:
                        pass
                raise TypeError(
                    f'{dikt}(type: {type(dikt)}) is not matched by {klass}')

        try:
            if dataclasses.is_dataclass(klass):
                a = klass(**dikt)
                logger.error(a)
                return a
            a = klass(dikt)
            return a
        except Exception as e:
            etype, value, tb = sys.exc_info()
            if convert_failed_continue is True:
                logger.warning(
                    'Failed to convert {}(type: {}) to {} type, so no convert it, because {}',
                    dikt, type(dikt), klass, e)
            else:
                if logger_exception is True:
                    perr.logger_exception(etype, value, tb)
                raise TypeError(
                    f'Failed to convert {dikt}(type: {type(dikt)}) to {klass} type, because {e}'
                ) from e
    return dikt


units = {
    'B': 1,
    'b': 1,
    'K': 2**10,
    'KB': 2**10,
    'M': 2**20,
    'MB': 2**20,
    'G': 2**30,
    'GB': 2**30,
    'T': 2**40,
    'TB': 2**40,
}


def parse_size(human_readable_size, unit=None):
    if unit is None:
        pattern = r'(?P<size>\d+(.\d+)*) *(?P<unit>([K|M|G|T]B*|(B|b)))'
        match = re.match(pattern, human_readable_size)
        if match is None:
            raise ValueError(f'{human_readable_size} cannot parse to byte')
        return parse_size(match.group('size'), match.group('unit'))
    size = float(human_readable_size)
    return int(size * units[unit])
