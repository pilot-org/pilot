import enum
import functools
import dataclasses
import asyncio
import contextlib
import inspect
from typing import (List, Dict, Any, Callable, Optional)
from loguru import logger

from . import core

_hook_map_by_name = {}


class HookOccasion(enum.Flag):
    PRE = enum.auto()
    POST = enum.auto()


@dataclasses.dataclass
class HookSetting:
    occasion: HookOccasion
    callback: Callable[
        [HookOccasion, List[Any], Dict[str, Any], Optional[Any]], None]


class _HookEngine:
    def __init__(self):
        self._hook_settings = {}
        self._register_id = 0

    @contextlib.contextmanager
    def register(self, hook, setting):
        try:
            i = self._register_id
            self._hook_settings[i] = (hook, setting)
            self._register_id += 1
            yield i
        finally:
            self._hook_settings.pop(i)

    def get_hook(self, i):
        return self._hook_settings[i]


_engine = _HookEngine()


class _Hook:
    def __init__(self, raw_func, engine, hook_next=None):
        self._raw_func = raw_func
        self._engine = engine
        self._hook_next = hook_next
        self._settings = {}

    @contextlib.contextmanager
    def register(self, setting):
        cm = contextlib.nullcontext(
        ) if self._hook_next is None else self._hook_next.register(setting)
        try:
            with self._engine.register(self, setting) as i:
                with cm:
                    self._ids[i] = setting
                    yield
        finally:
            self._ids.pop(i)

    def emit(self, occasion, args, kwargs):
        for setting in self._ids.values():
            try:
                if occasion & setting.occasion:
                    setting.callback(occasion, args, kwargs)
            except Exception as e:
                logger.warning(f'Occur unexpected error in hook: {e}')
        if self._hook_next is not None:
            self._hook_next.emit(occasion, args, kwargs)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._async_call(
            *args, **kwargs) if inspect.iscoroutinefunction(
                self._raw_func) else self._call(*args, **kwargs)

    async def _async_call(self, *args, **kwargs):
        self.emit(HookOccasion.Pre, args, kwargs, None)
        res = await self._raw_func(*args, **kwargs)
        self.emit(HookOccasion.Pre, args, kwargs, res)

    def _async_call(self, *args, **kwargs):
        self.emit(HookOccasion.Pre, args, kwargs, None)
        res = self._raw_func(*args, **kwargs)
        self.emit(HookOccasion.Pre, args, kwargs, res)


def may_hook(raw_func, engine=_engine):
    return functools.update_wrapper(_Hook(raw_func, engine), raw_func)


class HookEntry:
    @staticmethod
    def _add_hook(name, entry):
        if name in _hook_map_by_name.keys():
            raise core.UsageError(f'{name} was registered, please use another')
        _hook_map_by_name[name] = entry

    def __init__(self):
        self._callees = []

    def register(self, callee):
        self._callees.append(callee)

    def unregister(self, callee):
        self._callees.remove(callee)

    async def emit(self, tags, info):
        tasks = [callee(tags) for callee in self._callees]
        await asyncio.gather(*tasks)


class Tester(contextlib.ExitStack):
    test_infos = []

    @staticmethod
    def add_test(hook, marks, **kwargs):
        def wrap(test_func):
            Tester.test_infos.append((test_func, hook, marks, kwargs))
            return test_func

        return wrap

    @staticmethod
    @contextlib.contextmanager
    def as_test(test_func, hook, checker, match_tags=[], reject_tags=[]):
        async def func(tags):
            if any([match_tag not in tags for match_tag in match_tags]):
                return
            if any([reject_tag in tags for reject_tag in reject_tags]):
                return
            r = test_func(checker)
            if inspect.iscoroutinefunction(r):
                await r

        if isinstance(hook, HookEntry):
            pass
        elif hook in _hook_map_by_name.keys():
            hook = _hook_map_by_name[hook]
        else:
            raise core.UsageError(f'Cannot find {hook}')

        hook.register(func)
        yield
        hook.unregister(func)

    def __init__(self, checker):
        self._checker = checker

    def add_test_by_mark(self, *required_marks):
        for test_func, hook, marks, kwargs in Tester.test_infos:
            if any([
                    required_mark not in marks
                    for required_mark in required_marks
            ]):
                continue
            self.enter_test(test_func, hook, **kwargs)

    def enter_test(self, test_func, hook, **kwargs):
        self.enter_context(
            Tester.as_test(test_func, hook, self._checker, **kwargs))
