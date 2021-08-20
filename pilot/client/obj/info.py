from __future__ import annotations
import sys
import functools
import collections
import enum
import asyncio
import anyio
from abc import abstractmethod
from loguru import logger
from typing import (
    Generic,
    NamedTuple,
    Callable,
    Type,
    Tuple,
    TypeVar,
    Optional,
    Set,
    Dict,
    Any,
    overload,
)

from . import core as pcore
from .error import ObjUsage

Spec = TypeVar('Spec', bound='_CachedInfoSpec')
Getter = TypeVar('Getter', bound='_CachedInfoGetterBase')
Entry = TypeVar('Entry', bound='CachedInfoGroupEntry')
Obj = TypeVar('Obj', bound=pcore.Obj)
Cached = TypeVar('Cached')
DependInfo = TypeVar('DependInfo', bound='_DependInfo')
InfoId = TypeVar('InfoId', bound='_InfoId')
#Func = TypeVar('Func', Callable[[Obj, Cmd], Cached], Callable[[Obj], Cached])


def _check_can_use_cached_info(cls, name):
    if not issubclass(cls, pcore.Obj):
        raise ObjUsage(
            f'{name} only can be used in Obj, but {cls} is not this.')


def _get_class_from_frame(frame):
    import inspect
    args, _, _, value_dict = inspect.getargvalues(frame)
    if len(args) and args[0] == 'self':
        instance = value_dict.get('self', None)
        if instance:
            return getattr(instance, '__class__', None)
    return None


class _TraceResult(enum.Enum):
    ADD_NEW_ONE = enum.auto()
    NOT_FOUND = enum.auto()
    FAILED = enum.auto()


class _DependGraph:
    def __init__(self, depth) -> None:
        self._depth = depth
        self._specs_by_func_name: Dict[Tuple[Type[Obj], str], Spec] = {}

    def register_spec(self, spec, func_cls, func_name):
        if (func_cls, func_name) in self._specs_by_func_name.keys():
            raise ObjUsage(
                f'Info by cls({func_cls} and function({func_name} is registered.'
            )
        self._specs_by_func_name[(func_cls, func_name)] = spec

    def trace_and_add_depend(self,
                             info_id: _InfoId,
                             ignore_depth_plus: int = 0) -> _TraceResult:
        ignore_depth_plus += 1
        for i in range(ignore_depth_plus, self._depth):
            try:
                frame = sys._getframe(i)
            except ValueError:
                return _TraceResult.NOT_FOUND
            func_name = frame.f_code.co_name
            func_cls = _get_class_from_frame(frame)

            if func_cls is not None:
                the_spec_used_this = self._specs_by_func_name.get(
                    (func_cls, func_name))
                if the_spec_used_this is not None:
                    if the_spec_used_this.add_depend(info_id.to_depend_info()):
                        logger.debug('Detect that {} depneds on {}', func_name,
                                     info_id)
                        return _TraceResult.ADD_NEW_ONE
                    else:
                        return _TraceResult.NOT_FOUND
        logger.warning('Cannot trace all frame to get dependency in depth {}',
                       self._depth)
        return _TraceResult.FAILED


class _CachedInfoGetterBase(Generic[Spec, Cached]):
    _cached_value: Cached

    def __init__(self, spec: Spec, obj: Obj, info_id: InfoId):
        self._info_id = info_id
        self._is_cached: bool = False

        self._get_func = functools.partial(spec.func, obj, *info_id.args,
                                           **info_id.kwargs)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} info_id={self._info_id}>'

    @abstractmethod
    def get(self) -> Cached:
        pass

    @abstractmethod
    def clean_cache(self) -> None:
        pass


class _AsyncCachedInfoGetter(_CachedInfoGetterBase):
    def __init__(self, spec: Spec, obj: Obj, info_id: InfoId):
        super().__init__(spec, obj, info_id=info_id)
        self._lock = anyio.Lock()

    def get(self) -> Cached:
        get_func = self._get_func

        @functools.wraps(get_func)
        async def load_value():
            async with self._lock:
                if self._is_cached:
                    logger.debug('{} gets {} from cache', self,
                                 self._cached_value)
                    return self._cached_value
                value = await get_func()
                self._cached_value = value
                self._is_cached = True
                logger.debug('{} gets {} and stores it to cache', self, value)

                self._info_id.trace_and_add_depend(1)
                return value

        return load_value()

    def clean_cache(self, due_to: Optional[str] = None) -> None:
        # TODO: lock this
        because = '' if due_to is None else f'Because deleting is trigger by {due_to}. '
        if self._is_cached:
            logger.debug('{}Clean cache in {}: {}', because, self,
                         self._cached_value)
        else:
            logger.debug('{}Clean cache in {}, but nothing is cached.',
                         because, self)
        self._is_cached = False


class _CachedInfoGetter(_CachedInfoGetterBase):
    # TODO:
    def get(self) -> Cached:
        if self._is_cached:
            return self._cached_value
        value = self._get_func()
        self._cached_value = value
        return value

    def clean_cache(self) -> None:
        # TODO: lock this
        self._is_cached = False


def _new_cached_info_getter(spec: Spec, obj: Obj, info_id: InfoId):
    cls = _AsyncCachedInfoGetter if asyncio.iscoroutinefunction(
        spec.func) else _CachedInfoGetter
    return cls(spec, obj, info_id=info_id)


class _DependInfo(NamedTuple):  #Generic[Spec]
    spec: Spec
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]

    def __hash__(self):
        hash_kwargs = hash(tuple(sorted(self.kwargs.items())))
        return hash((self.spec.__class__, self.args, hash_kwargs))

    @classmethod
    def gen(cls, spec: Spec, *args, **kwargs):
        return cls(spec, args, kwargs)

    def to_info_id(self, obj_id: Optional[pcore.ID]):
        return _InfoId(self.spec, obj_id, *self.args, **self.kwargs)


class _InfoId:
    def __init__(self, spec: Spec, obj_id: Optional[pcore.ID], *args,
                 **kwargs) -> None:
        self._spec: Spec = spec
        self._obj_id: Optional[pcore.ID] = obj_id
        self._args: Tuple[Any, ...] = args
        self._kwargs: Dict[str, Any] = kwargs

    def __repr__(self) -> str:
        spec_str = f' spec={self._spec}'
        id_str = '' if self._obj_id is None else f' obj_id={self._obj_id}'
        args_str = f' args={self._args}' if self._args else ''
        kwargs_str = f' kwargs={self._kwargs}' if self._kwargs else ''
        return f'<{self.__class__.__name__}{spec_str}{id_str}{args_str}{kwargs_str}>'

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self):
        hash_kwargs = hash(tuple(sorted(self._kwargs.items())))
        return hash((self._spec, self._obj_id, self._args, hash_kwargs))

    @property
    def args(self) -> Tuple[Any, ...]:
        return self._args

    @property
    def kwargs(self) -> Dict[str, Any]:
        return self._kwargs

    def to_depend_info(self) -> _DependInfo:
        return _DependInfo(self._spec, self._args, self._kwargs)

    def find_getter(self, obj: Obj, info_getter_stores: Dict[_InfoId,
                                                             Any]) -> Getter:

        getter = info_getter_stores.get(self)
        if getter is None:
            getter = _new_cached_info_getter(self._spec, obj, info_id=self)
            info_getter_stores[self] = getter
        return getter

    def trace_and_add_depend(self, ignore_depth_plus=0) -> _TraceResult:
        return self._spec.graph.trace_and_add_depend(self,
                                                     ignore_depth_plus + 1)


@overload
def _depend_to_set(item: None) -> Set[_DependInfo]:
    ...


@overload
def _depend_to_set(item: collections.abc.Iterable[Spec]) -> Set[_DependInfo]:
    ...


@overload
def _depend_to_set(item: Spec) -> Set[_DependInfo]:
    ...


def _depend_to_set(item):
    if item is None:
        depends = set()
    elif isinstance(item, collections.abc.Iterable):
        depends = set(item)
    elif isinstance(item, _CachedInfoSpec):
        depends = {_DependInfo.gen(item)}
    else:
        raise NotImplementedError(f'Cannot handle {item} {type(item)}')
    return depends


class _CachedInfoSpec(Generic[Obj, Cached]):
    __slots__ = '_func', '_depend_infos'

    def __init__(self, *, graph: _DependGraph, depend) -> None:
        self._graph: _DependGraph = graph
        self._depend_infos: Set[_DependInfo] = _depend_to_set(depend)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} of {self.func.__name__}>'

    @property
    @abstractmethod
    def func(self):
        pass

    @property
    def graph(self) -> _DependGraph:
        return self._graph

    @property
    def field_name(self) -> str:
        return self._field_name

    @property
    def obj_cls(self):
        return self._cls

    @property
    def id_needed(self) -> bool:
        return issubclass(self._cls, pcore.IdIdentifiedObj)

    def __set_name__(self, cls, name: str):
        _check_can_use_cached_info(cls, name)
        self._cls = cls
        self._field_name: str = name
        self._graph.register_spec(self, cls, name)

    def add_depend(self, depend_info: _DependInfo) -> bool:
        if depend_info in self._depend_infos:
            return False
        self._depend_infos.add(depend_info)
        return True


class _CachedInfoFuncSpec(_CachedInfoSpec):
    # TODO: support to clean cache
    def __init__(self, func: Callable[[Obj], Cached], *, graph: _DependGraph,
                 depend):
        super().__init__(graph=graph, depend=depend)
        self._func: Callable[[Obj], Cached] = func

    @property
    def func(self) -> Callable[[Obj], Cached]:
        return self._func

    def __get__(self, obj, cls):
        if obj is None:
            return self
        return functools.partial(self, obj)

    def __call__(self, obj, *args, **kwargs):
        # TODO: support general args
        # TODO: check args and kwargs must be hashable
        info_id = _InfoId(self, obj.id, *args, **kwargs)
        info_getter_stores = obj.owner.info_getter_stores
        getter = info_id.find_getter(obj, info_getter_stores)
        return getter.get()


class _CachedInfoPropertySpec(_CachedInfoSpec):
    '''treat as a spec, so it has function and not client'''
    def __init__(self, func, *, graph: _DependGraph,
                 depend: Optional[_DependInfo]):
        super().__init__(graph=graph, depend=depend)
        self._func = func

    @property
    def func(self):
        return self._func

    def __get__(self, obj, cls):
        if obj is None:
            return self

        if not isinstance(obj, pcore.Obj):
            raise ObjUsage(
                f'Info of {self._func} must be a member of Obj, not {cls}')

        info_getter_stores = obj.owner.info_getter_stores

        info_id = _InfoId(self, obj.id)
        getter = info_id.find_getter(obj, info_getter_stores)
        return getter.get()

    def __delete__(self, obj):
        '''it will ignore error: del a non-cached value'''
        info_getter_stores = obj.owner.info_getter_stores

        info_id = _InfoId(self, obj.id)
        getter = info_id.find_getter(obj, info_getter_stores)
        getter.clean_cache(due_to=self)
        for depend_info in self._depend_infos:
            depended_info_id = depend_info.to_info_id(obj.id)
            getter = depended_info_id.find_getter(obj, info_getter_stores)
            getter.clean_cache(due_to=self)


class _InfoGroupPropertyGetter(Generic[Entry]):
    def __init__(self, entry_cls: Type[Entry]):
        self._src_cls = entry_cls

    def __set_name__(self, cls, name):
        _check_can_use_cached_info(cls, name)
        self._used_by_cls = cls
        self._field_name = name

    def __repr__(self) -> str:
        return f'<{self._field_name} of {self._used_by_cls}>'

    @overload
    def __get__(self, obj: None, cls) -> Type[Entry]:
        ...

    @overload
    def __get__(self, obj: Obj, cls) -> Entry:
        ...

    def __get__(self, obj, cls):
        if obj is None:
            return self._src_cls
        return self._src_cls(parent=obj, owner=obj.owner)


class CachedInfoGroupEntry(pcore.ProxyObj):
    @classmethod
    def as_property(cls: Type[Entry]) -> _InfoGroupPropertyGetter[Entry]:
        return _InfoGroupPropertyGetter(cls)

    def __init__(self, *, parent, owner):
        super().__init__(parent=parent, owner=owner)
        self._parent = parent

    def __repr__(self) -> str:
        id_str = '' if self.id is None else f' id={self.id}'
        return f'<{self.__class__.__name__}{id_str}>'

    def _check(self):
        if self._just_spec is False:
            raise ObjUsage()


_graph: _DependGraph = _DependGraph(100)

depend = _DependInfo.gen


@overload
def cached_info(depend: Callable[[Obj], Cached] = ...,
                graph: _DependGraph = ...,
                depend_on_id: bool = ...):
    ...


@overload
def cached_info(depend: None = ...,
                graph: _DependGraph = ...,
                depend_on_id: bool = ...):
    ...


@overload
def cached_info(depend: collections.abc.Iterable[Spec],
                graph: _DependGraph = ...,
                depend_on_id: bool = ...):
    ...


@overload
def cached_info(depend: Spec,
                graph: _DependGraph = ...,
                depend_on_id: bool = ...):
    ...


def cached_info(depend=None,
                graph: _DependGraph = _graph,
                depend_on_id: bool = True):
    if callable(depend) and not isinstance(depend, _CachedInfoSpec):
        return cached_info()(depend)

    def decorater(func: Callable[[Obj], Cached]) -> _CachedInfoFuncSpec:
        spec = _CachedInfoFuncSpec(func, graph=graph, depend=depend)
        return spec

    return decorater


def cached_info_property(depend=None, graph=_graph):
    if callable(depend) and not isinstance(depend, _CachedInfoSpec):
        return cached_info_property()(depend)

    def decorater(func):
        spec = _CachedInfoPropertySpec(func, graph=graph, depend=depend)
        return spec

    return decorater
