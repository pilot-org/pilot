import contextlib
import asyncio
from typing import (
    Generic,
    Optional,
    Dict,
    Set,
    Callable,
    Any,
    TypeVar,
    Type,
    overload,
)
from loguru import logger

from pilot import error as perr
from . import core as pcore
from . import info as pinfo
from . import state as pstate
from .error import ObjUsage

Obj = TypeVar('Obj', bound=pcore.Obj)
_Action = TypeVar('_Action', bound='Action')
Result = TypeVar('Result')


class _UnexpectedStateError(Exception):
    pass


class _Acting(pinfo.CachedInfoGroupEntry, Generic[_Action, Result]):
    def __init__(self, action: _Action, obj: Obj, func_result: Result,
                 wanted_state: pstate._State, *, parent, owner):
        super().__init__(parent=parent, owner=owner)
        self._action: _Action = action
        self._obj: Obj = obj
        self._result: Result = func_result
        self._wanted_state: pstate._State = wanted_state
        self._is_finished: bool = False

    def __iter__(self):
        pass

    @property
    def obj(self) -> Obj:
        return self._obj

    @property
    def exit_state(self) -> pstate._State:
        if self._is_finished is False:
            raise RuntimeError('Action is not finished.')
        return self._exit_state

    async def peek(self) -> pstate._State:
        pass

    async def wait_finish(self,
                          stop_state: Optional[pstate._State] = None,
                          max_get: Optional[int] = None,
                          interval: Optional[int] = None) -> '_Acting':
        max_get = max_get or self._action.state_max_get
        interval = interval or self._action.state_interval

        def clean_cache():
            self._action.clean_cache(obj=self._obj)

        @perr.retry(_UnexpectedStateError,
                    max_get=max_get,
                    interval=interval,
                    when_retry_it=clean_cache)
        async def wait_finish() -> pstate._State:
            candidate_states = [self._wanted_state]
            if stop_state is not None:
                candidate_states.append(stop_state)
            try:
                current_state = await self._action.get_current_state(
                    candidate_states, obj=self._obj)
                matched_by_stop_state = current_state in candidate_states
                matched_by_wanted_state = current_state in candidate_states
                if matched_by_stop_state or matched_by_wanted_state:
                    return current_state
                raise _UnexpectedStateError(
                    f'Expect state in {candidate_states}, but get {current_state}'
                )
            except Exception as e:
                logger.debug('wait failed due to {}', e)
                raise

        self._exit_state: pstate._State = await wait_finish()
        self._is_finished = True
        return self


class _CanCancelActing(_Acting):
    def cancel(self):
        pass


# TODO: add command
class _ActionProperty(Generic[_Action]):
    def __init__(self, cls: Type[_Action], **kwargs):
        self._action_cls: Type[_Action] = cls
        self._kwargs: Dict[str, Any] = kwargs

    def __set_name__(self, cls, name: str):
        self._name: str = name

    @overload
    def __get__(self, obj: None, cls) -> Type[_Action]:
        ...

    @overload
    def __get__(self, obj: Obj, cls) -> _Action:
        ...

    def __get__(self, obj, cls):
        if obj is None:
            return self._action_cls
        if not isinstance(obj, pcore.Obj):
            raise ObjUsage(
                f'{cls.__name__} must be property of Obj and is not {type(obj)}({obj})'
            )
        return self._action_cls(obj,
                                parent=obj,
                                owner=obj.owner,
                                attr_name=self._name,
                                **self._kwargs)


def do_nothing(*args, **kwargs):
    pass


class Action(pcore.ProxyObj, Generic[Obj, Result]):
    func_max_get: int = 1
    func_interval: int = 0
    state_max_get: int = 3
    state_interval: int = 1
    source_state: Set[pstate._State] = set()
    can_cancel: bool = False

    @classmethod
    def as_property(
        cls,
        trigger_act_func: Callable[..., Result],
        clean_cache_func: Callable[[Obj, Obj], None],
        wanted_next_state: pstate._State,
        source_state: Optional[Set[pstate._State]] = None,
        is_for_creating=False,
        func_max_get: Optional[int] = None,
        func_interval: Optional[int] = None,
        state_max_get: Optional[int] = None,
        state_interval: Optional[int] = None,
        **kwargs,
    ) -> _ActionProperty[_Action]:
        return _ActionProperty(
            cls,
            trigger_act_func=trigger_act_func,
            clean_cache_func=clean_cache_func,
            wanted_next_state=wanted_next_state,
            source_state=source_state,
            is_for_creating=is_for_creating,
            func_max_get=func_max_get,
            func_interval=func_interval,
            state_max_get=state_max_get,
            state_interval=state_interval,
            **kwargs,
        )

    def __init__(
        self,
        obj: Obj,
        *,
        trigger_act_func: Callable[..., Result],
        clean_cache_func: Callable[[Obj, Obj], None],
        wanted_next_state: pstate._State,
        source_state: Optional[Set[pstate._State]],
        is_for_creating,
        func_max_get: Optional[int],
        func_interval: Optional[int],
        state_max_get: Optional[int],
        state_interval: Optional[int],
        parent,
        owner,
        attr_name,
    ):
        super().__init__(parent=parent, owner=owner)
        self._obj: Obj = obj
        self._trigger_act_func: Callable[..., Result] = trigger_act_func
        self._clean_cache_func: Callable[[Obj, Obj], None] = clean_cache_func
        self._wanted_next_state = wanted_next_state
        self._source_state: Set[
            pstate._State] = source_state or self.source_state
        self._is_for_creating = is_for_creating
        self.func_max_get: int = func_max_get or self.func_max_get
        self.func_interval: int = func_interval or self.func_interval
        self.state_max_get: int = state_max_get or self.state_max_get
        self.state_interval: int = state_interval or self.state_interval
        self._attr_name: str = attr_name

    def __repr__(self):
        return f'<Acting on {self._name}>'

    @property
    def name(self):
        return f'Action({self._name})'

    @property
    def _name(self):
        return f'{self._obj.__class__}.{self._trigger_act_func.__name__}'

    def clean_cache(self, *, obj) -> None:
        self._clean_cache_func(self._obj, obj)

    async def get_current_state(self, extra_state=[], *, obj) -> pstate._State:
        matched = set()

        async def func(state):
            if await state.check(obj):
                matched.add(state)

        tasks = [func(state) for state in self._source_state
                 ] + [func(state) for state in extra_state]
        await asyncio.gather(*tasks)

        if len(matched) != 1:
            raise _UnexpectedStateError(
                f'Must match only one, but get {[ m for m in matched]} (len: {len(matched)})'
            )

        return next(iter(matched))

    @contextlib.asynccontextmanager
    async def _get_created_obj_when_trigger_time(self, setter, owner_of_action,
                                                 *args, **kwargs):
        try:
            yield
        finally:
            setter(self._obj)

    @contextlib.contextmanager
    def register_hook(self):
        pass

    async def __call__(self,
                       *args,
                       exception=Exception,
                       max_get: Optional[int] = None,
                       interval: Optional[int] = None,
                       **kwargs):
        # TODO: record action failed time
        max_get = max_get or self.func_max_get
        interval = interval or self.func_interval

        @perr.retry(exception, max_get=max_get, interval=interval)
        async def trigger() -> Result:
            return await self._trigger_act_func(self._obj, *args, **kwargs)

        obj = self._obj
        if self._is_for_creating:

            def set_created_obj(target):
                nonlocal obj
                obj = target

            cm = self._get_created_obj_when_trigger_time(
                set_created_obj, self._obj, *args, **kwargs)
        else:
            # because of no nullcontext for async
            cm = contextlib.AsyncExitStack()

        async with cm:
            res: Result = await trigger()

        next_state: pstate._State = self._wanted_next_state

        if self._is_for_creating:
            logger.info('{}.{} trigger {} and the next wanted state is {}',
                        self._obj, self._attr_name,
                        self._trigger_act_func.__name__, next_state)
        else:
            current_state: pstate._State = await self.get_current_state(obj=obj
                                                                        )
            if not self._is_for_creating and current_state == next_state:
                raise ObjUsage(
                    f'Current state is aleady {next_state}, which you wnated to transform to again by {self.name}.'
                )
            logger.info(
                '{}.{} trigger {} and expect that state transforms {} to {}',
                self._obj, self._attr_name, self._trigger_act_func.__name__,
                current_state, next_state)

        acting_cls = _CanCancelActing if self.can_cancel else _Acting
        return acting_cls(self,
                          obj,
                          res,
                          next_state,
                          parent=self._parent,
                          owner=self.owner)


class RetryActionProperty:
    pass
