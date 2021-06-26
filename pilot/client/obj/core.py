from __future__ import annotations
from abc import abstractclassmethod, abstractmethod
import functools
import unittest
from typing import (
    Generic,
    TYPE_CHECKING,
    NoReturn,
    TypeVar,
    Union,
    overload,
)

if TYPE_CHECKING:
    from . import info_core as pinfo

ID = TypeVar('ID', int, str)


class ClientInterface:
    def __init__(self, *, client, checker: unittest.TestCase):
        self._client = client
        self._checker: unittest.TestCase = checker

    @property
    def client(self):
        return self._client

    @property
    def checker(self):
        return self._checker


class ClientIdIdentifyInterface(ClientInterface):
    def __init__(self, id, **kwargs):
        super().__init__(**kwargs)
        self._id = id

    @functools.cached_property
    def id(self):
        return self._id() if callable(self._id) else self._id


class ClientObj:
    def __init__(self, it: ClientInterface):
        self._it = it

    @property
    def it(self):
        return self._it


class ClientIdIdentifyObj(ClientObj):
    def __init__(self, it: ClientIdIdentifyInterface):
        self._it = it

    def __repr__(self):
        return f'<{self.__class__} id={self.id}>'

    @property
    def id(self):
        return self._it.id

    @property
    def it(self):
        return self._it

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.id == other.id


class ClientObjGetter(ClientObj):
    interface_cls = ClientInterface
    id_identify_interface_cls = ClientIdIdentifyInterface

    def __init__(self, *args, **kwargs):
        self._kwargs_for = kwargs
        super().__init__(self.new_interface())

    @property
    def getter_kwargs(self):
        return self._kwargs_for_new

    def new_interface(self):
        return self.interface_cls(**self._kwargs_for_new)

    def new_id_interface(self, id):
        return self.id_identify_interface_cls(id, **self._kwargs_for_new)


from typing import (
    TYPE_CHECKING,
    runtime_checkable,
    Dict,
    Any,
    Protocol,
)


@runtime_checkable
class ObjStorable(Protocol):
    '''Please access this value by info obj.'''
    @property
    def obj_stores(self) -> Dict[int, 'Obj']:
        ...

    @property
    def info_getter_stores(self) -> Dict[int, pinfo._CachedInfoGetterBase]:
        ...


class Obj:
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
        candidate_obj = super(_Obj, cls).__new__(cls)
        obj_id = candidate_obj.id
        obj = owner.obj_stores.get(obj_id)
        if obj is None:
            owner.obj_stores[obj_id] = candidate_obj
            return candidate_obj
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
    def __init__(self, obj_id: ID, owner: ObjStorable):
        super().__init__(owner=owner)
        self._id: ID = obj_id

    @property
    def id(self) -> ID:
        return self._id


class ProxyObj(_Obj):
    def __init__(self, parent):
        super().__init__(parent.owner)
        self._parent = parent

    @property
    def id(self):
        return self._parent.id


class ObjOwner(Obj):
    '''Owner of obj is also a obj'''
    def __init__(self) -> None:
        super().__init__()
        self._obj_stores: Dict[int, 'Obj'] = {}
        self._info_getter_stores: Dict[int, pinfo._CachedInfoGetterBase] = {}

    # following methods are for ObjStorable
    @property
    def obj_stores(self) -> Dict[int, 'Obj']:
        return self._obj_stores

    @property
    def info_getter_stores(self) -> Dict[int, pinfo._CachedInfoGetterBase]:
        return self._info_getter_stores

    # following methods are for Obj
    @property
    def owner(self):
        return self
