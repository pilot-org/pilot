from __future__ import annotations
from loguru import logger
from abc import (
    ABC,
    abstractmethod,
)
from typing import (
    Generic,
    TYPE_CHECKING,
    Optional,
    TypeVar,
    runtime_checkable,
    Dict,
    Any,
    Protocol,
)

if TYPE_CHECKING:
    from . import info_core as pinfo

ID = TypeVar('ID', int, str, None)


@runtime_checkable
class ObjStorable(Protocol):
    '''Please access this value by info obj.'''
    @property
    def obj_stores(self) -> Dict[int, 'Obj']:
        ...

    @property
    def info_getter_stores(self) -> Dict[int, pinfo._CachedInfoGetterBase]:
        ...


class Obj(ABC):
    def __init__(self) -> None:
        self._info_stores: Dict[int, Any] = {}

    @abstractmethod
    def owner(self):
        pass

    @property
    @abstractmethod
    def id(self):
        # TODO: support int and str
        pass


class _Obj(Obj):
    def __new__(cls, *args, owner: ObjStorable, **kwargs):
        # TODO: remove workaround
        if issubclass(cls, SingletonObj):
            obj_id = None
        elif issubclass(cls, IdIdentifiedObj):
            obj_id = kwargs['obj_id']
        elif issubclass(cls, ProxyObj):
            obj_id = kwargs['parent'].id
        else:
            raise TypeError(f'Unknown type: {cls}')

        hash_id = (
            cls,
            obj_id,
        )
        obj = owner.obj_stores.get(hash_id)
        if obj is None:
            new_obj = super(_Obj, cls).__new__(cls)
            owner.obj_stores[hash_id] = new_obj
            return new_obj
        return obj

    def __init__(self, *, owner):
        super().__init__()
        self._owner = owner

    @property
    def owner(self):
        return self._owner


class SingletonObj(_Obj):
    '''Each client has only this info'''
    @property
    def id(self) -> None:
        return None


class IdIdentifiedObj(_Obj, Generic[ID]):
    def __init__(self, obj_id: ID, *, owner: ObjStorable):
        super().__init__(owner=owner)
        self._id: ID = obj_id

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} id={self.id}>'

    @property
    def id(self) -> ID:
        return self._id


class ProxyObj(_Obj):
    def __init__(self, *, parent, owner):
        self._parent = parent
        super().__init__(owner=owner)

    @property
    def id(self):
        return self._parent.id


class ObjOwner(Obj):
    '''Owner of obj is also a obj'''
    def __init__(self) -> None:
        super().__init__()
        self._obj_stores: Dict[Optional[int], 'Obj'] = {}
        # TODO: with lock
        self._info_getter_stores: Dict[int, pinfo._CachedInfoGetterBase] = {}

    # following methods are for ObjStorable
    @property
    def obj_stores(self) -> Dict[Optional[int], 'Obj']:
        return self._obj_stores

    @property
    def info_getter_stores(self) -> Dict[int, pinfo._CachedInfoGetterBase]:
        return self._info_getter_stores

    # following methods are for Obj
    @property
    def owner(self):
        return self

    @property
    def id(self) -> None:
        return None
