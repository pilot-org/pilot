import contextlib
import asyncio
import dataclasses
import asyncclick as click
from typing import (List, Callable, Any)
from loguru import logger

from pilot import error as perr
from . import core as pcore
from . import state as pstate


@dataclasses.dataclass
class _StateMapping:
    _from: pstate.StateEnum
    _to: pstate.StateEnum


class _UnexpectedStateError(Exception):
    pass


class _Acting(pcore.ClientObj):
    def __init__(self, action, func_result, wanted_state):
        super().__init__(action.it)
        self._action = action
        self._result = func_result
        self._wanted_state = wanted_state

    def __iter__(self):
        pass

    async def is_finish(self, stop_state=None):
        stop_state = stop_state or self._wanted_state
        return await self._action.get_current_state([stop_state]) == stop_state

    async def peek(self):
        pass

    async def wait_finish(self, stop_state=None, max_get=None, interval=None):
        max_get = max_get or self._action.state_max_get
        interval = interval or self._action.state_interval

        @perr.retry(_UnexpectedStateError, max_get=max_get, interval=interval)
        async def wait_finish():
            nonlocal stop_state
            stop_state = stop_state or self._wanted_state
            current_state = await self._action.get_current_state([stop_state])
            if current_state != stop_state:
                self._action.clean_cache()
                raise _UnexpectedStateError(
                    f'Expect {stop_state}, but get {current_state}')

        await wait_finish()


class _CanCancelActing(_Acting):
    def cancel(self):
        pass


class Action(pcore.ClientObj):
    func_max_get = 1
    func_interval = 0
    state_max_get = 3
    state_interval = 1
    source_state = {}
    can_cancel = False

    def __init__(self,
                 obj,
                 *,
                 act_func,
                 source_state=None,
                 func_max_get=None,
                 func_interval=None,
                 state_max_get=None,
                 state_interval=None):
        super().__init__(obj.it)
        self._obj = obj
        self._act_func = act_func
        self._source_state = source_state or self.source_state
        self.func_max_get = func_max_get or self.func_max_get
        self.func_interval = func_interval or self.func_interval
        self.state_max_get = state_max_get or self.state_max_get
        self.state_interval = state_interval or self.state_interval

    def _clean_cache(self, target_obj):
        pass

    def get_next_state(self, current_state):
        pass

    def get_act_result(self, args, kwargs, raw_result):
        return raw_result

    def __repr__(self):
        return f'<Acting on {self._obj.__class__}.{self._act_func.__name__}>'

    def clean_cache(self):
        self._clean_cache(self._obj)

    async def get_current_state(self, extra_state=[]):
        matched = set()

        async def func(state):
            if await state.check(self._obj):
                matched.add(state)

        tasks = [func(state) for state in self._source_state
                 ] + [func(state) for state in extra_state]
        await asyncio.gather(*tasks)

        if len(matched) != 1:
            raise _UnexpectedStateError(
                f'Must match only one, but get {[ m for m in matched]} (len: {len(matched)})'
            )

        return next(iter(matched))

    @contextlib.contextmanager
    def register_hook(self):
        pass

    async def __call__(self,
                       *args,
                       exception=Exception,
                       max_get=None,
                       interval=None,
                       **kwargs):
        # TODO: record action failed time
        max_get = max_get or self.func_max_get
        interval = interval or self.func_interval

        current_state = await self.get_current_state()
        next_state = self.get_next_state(current_state)
        if current_state == next_state:
            raise click.UsageError(f'Current is aleady {next_state}')
        logger.info('{} expects {} to {}', self, current_state, next_state)

        @perr.retry(exception, max_get=max_get, interval=interval)
        async def func():
            res = await self._act_func(self._obj, *args, **kwargs)
            acting_cls = _CanCancelActing if self.can_cancel else _Acting
            return acting_cls(self, res, next_state)

        return await func()


def do_nothing(*args, **kwargs):
    pass


# TODO: add command
class _ActionProperty:
    def __init__(self, cls, **kwargs):
        self._action_cls = cls
        self._kwargs = kwargs

    def __get__(self, obj, cls):
        if obj is None:
            raise click.UsageError(f'')
        if isinstance(obj, pcore.ClientInterface):
            raise click.UsageError(f'')
        return self._action_cls(obj, **self._kwargs)


class RetryActionProperty:
    pass


def has_state_action(cls=Action, **kwargs):
    return _ActionProperty(cls, **kwargs)


class PlugAction(Action):
    state_max_get = 5

    def _clean_cache(self, drive):
        pass

    def get_next_state(self, current_state):
        pass

    def get_act_result(self, args, kwargs, raw_result):
        return raw_result


class Drive:
    def try_to_disable_drive(drive):
        pass

    plug_drive = has_state_action(cls=PlugAction,
                                  act_func=try_to_disable_drive,
                                  source_state={})
