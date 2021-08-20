import enum
import asyncio
import inspect
from loguru import logger

from .error import ObjUsage


class _StateOperatorEnum(enum.Enum):
    AND = '&'
    OR = '|'
    NONE = enum.auto()


def _merge(self, operator, other):
    if not isinstance(self, (_State, StateEnum)) or not isinstance(
            self, (_State, StateEnum)):
        raise ObjUsage(f'{other} must be instance of _State')
    elif isinstance(self, StateEnum):
        return _merge(_StateProxy(self.value), operator, other)
    elif isinstance(other, StateEnum):
        return _merge(self, operator, _StateProxy(other.value))
    elif self.operator == _StateOperatorEnum.NONE and other.operator == _StateOperatorEnum.NONE:
        return _MergeState(operator, self, other,
                           {self.unique_id, other.unique_id}, self._collector)
    elif self.operator == _StateOperatorEnum.NONE and other.operator != _StateOperatorEnum.NONE:
        new_ids = set(other.ids)
        new_ids.add(self.unique_id)
        return _MergeState(other.operator, self, other, new_ids,
                           self._collector)
    elif self.operator != _StateOperatorEnum.NONE and other.operator == _StateOperatorEnum.NONE:
        new_ids = set(self.ids)
        new_ids.add(other.unique_id)
        return _MergeState(self.operator, self, other, new_ids,
                           self._collector)
    elif self.operator != _StateOperatorEnum.NONE and self.operator != _StateOperatorEnum.NONE:
        if self.operator == other.operator and self.operator == operator:
            new_ids = set(self.ids)
            new_ids.union(other.ids)
            return _MergeState(self.operator, self, other, new_ids,
                               self._collector)
        return _MergeState(operator, self, other, [self, other],
                           self._collector)
    raise RuntimeError(f'Unknown')


class _State:
    # Cannot be hasnable, because StateEnum must be not hashable otherwise cannot judge the value that its content is equal but name is not equal
    def __init__(self, collector):
        self._collector = collector

    def __repr__(self):
        return f'<{self.__class__.__name__} {self._repr}>'

    @property
    def _repr(self):
        name = f'{self._enum_obj.__class__.__name__}.{self._enum_obj.name}' if hasattr(
            self, '_enum_obj') else f'{self.__class__.__name__}'
        return f'{name}({self.expression})'

    @property
    def operator(self):
        raise NotImplementedError

    @property
    def expression(self):
        raise NotImplementedError

    def __and__(self, other):
        return _merge(self, _StateOperatorEnum.AND, other)

    def __or__(self, other):
        return _merge(self, _StateOperatorEnum.OR, other)

    def set_enum_obj(self, obj):
        self._enum_obj = obj
        self._collector.register_enum(obj.__class__)

    @property
    def target_obj_type(self):
        return self._enum_obj.target_obj_type

    def _check_type_match(self, target_obj):
        if not isinstance(target_obj, self.target_obj_type):
            raise ObjUsage(
                f'Target obj type ({type(target_obj)}) of {target_obj} is not matched '
                f'to state needed ({self.target_obj_type}) on {self}')

    async def check(self, check_target, original_target=None):
        original_target = original_target or check_target
        result = await self._check(check_target, original_target)
        logger.debug('{} is {}on {} state by checking {}', original_target,
                     '' if result else 'not ', self, check_target)
        return result

    def _check(self, check_target, original_target):
        raise NotImplementedError

    def for_another_obj(self, get_another_obj_func):
        if isinstance(self, StateEnum):
            return self.value.for_another_obj(get_another_obj_func)
        return _StateProxy(self, get_another_obj_func)


def _first(obj):
    if isinstance(obj, _MergeState):
        return _first(obj._ids[0])
    if isinstance(obj, _UniqueState):
        return obj._unique_id
    return obj


class _MergeState(_State):
    def __init__(self, operator, left, right, ids, collector):
        super().__init__(collector)
        self._operator = operator
        self._left = left
        self._right = right
        self._ids = sorted(ids, key=_first)

    @property
    def expression(self):
        expressions = []
        for i in self._ids:
            # TODO: handle A & B & C == C & B & A and conside proxy
            if isinstance(i, _State):
                expressions.append(f'({i.expression})')
            else:
                expressions.append(str(i))
        return f' {self._operator.value} '.join(expressions)

    @property
    def ids(self):
        return self._ids

    @property
    def operator(self):
        return self._operator

    async def _check(self, check_target, original_target):
        async def check_for_each(state):
            self._check_type_match(check_target)
            return await state.check(check_target,
                                     original_target=original_target)

        tasks = [
            check_for_each(self._left),
            check_for_each(self._right),
        ]
        results = await asyncio.gather(*tasks)
        if self._operator == _StateOperatorEnum.AND:
            return all(results)
        elif self._operator == _StateOperatorEnum.OR:
            return any(results)
        raise ObjUsage(f'Unknown operator: {self._operator}')


class _StateProxy(_State):
    def __init__(self, parent, target_obj_transform=None):
        super().__init__(parent._collector)
        self._parent = parent
        self._target_obj_transform = target_obj_transform

    @property
    def operator(self):
        return self._parent.operator

    @property
    def expression(self):
        return self._parent.expression

    def __getattr__(self, key):
        return getattr(self._parent, key)

    def set_enum_obj(self, obj):
        if self._target_obj_transform is None:
            if self._parent.target_obj_type != obj.target_obj_type:
                raise ObjUsage(
                    f'Target obj type {obj.target_obj_type} of {self.__class__} is not matched '
                    f'to its parent {self._parent.target_obj_type} of {self._parent}'
                )
        super().set_enum_obj(obj)

    async def _check(self, check_target, original_target):
        if self._target_obj_transform is not None:
            check_target = self._target_obj_transform(check_target)
            if asyncio.iscoroutinefunction(self._target_obj_transform):
                check_target = await check_target
        # self._check_type_match(check_target)
        return await self._parent.check(check_target,
                                        original_target=original_target)


class _UniqueState(_State):
    def __init__(self, unique_id, collector):
        super().__init__(collector)
        self._unique_id = unique_id

    @property
    def expression(self):
        return str(self._unique_id)

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def operator(self):
        return _StateOperatorEnum.NONE

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            value = other
        elif isinstance(other, StateEnum):
            logger.warning('Detect that "{} == {}" was called', self, other)
            value = other.value
        else:
            return False
        return self._unique_id == value._unique_id

    async def _check(self, check_target, original_target):
        self._check_type_match(check_target)
        state = await self._enum_obj._get_unique_state(check_target)
        if inspect.iscoroutine(state):
            logger.warning(
                'Detect {} return coroutine object, please check _get_unique_state',
                self._enum_obj.__class__)
        if not isinstance(state, _State):
            logger.warning(
                'The value that return from _get_unique_state must be StateEnum type, but {} ({}) was gotten in {}',
                state, type(state), self)
        res = state.value == self
        logger.debug('(result) {} {} {} (expected)', state.value,
                     '=' if res else '!=', self)
        return res


class StateCollector:
    def __init__(self):
        self._id_count = 0
        self._unique_state_map = {}
        self._state_enum_group = set()

    def unique(self):
        unique_id = self._id_count
        self._id_count += 1
        value = _UniqueState(unique_id, self)
        self._unique_state_map[unique_id] = [value]
        return value

    def get_unique_state_main(self, unique_id):
        return self._unique_state_map[unique_id][0]

    def register_enum(self, enum_cls):
        self._state_enum_group.add(enum_cls)


class StateEnum(_State, enum.Enum):
    def __init__(self, value):
        if isinstance(value, StateEnum):
            value = _StateProxy(value.value)
        value.set_enum_obj(self)

    def __repr__(self):

        # because maybe value set by enum directly
        def get_value(target):
            if isinstance(target, StateEnum):
                return get_value(target.value)
            return target

        return f'<StateEnum {get_value(self.value)._repr}>'

    @classmethod
    async def matched_unique_states(cls, check_target):
        matched = set()

        async def func(unique_state):
            if isinstance(unique_state.value, _UniqueState):
                if await unique_state.value.check(check_target):
                    matched.add(unique_state)

        tasks = [
            func(unique_state) for unique_state in cls.__members__.values()
        ]
        await asyncio.gather(*tasks)

        return matched

    async def check(self, check_target):
        return await self.value.check(check_target)

    @property
    def target_obj_type(self):
        return self._get_target_obj_type()

    @classmethod
    def _get_target_obj_type(cls):
        raise NotImplementedError

    @classmethod
    async def _get_unique_state(self, check_target):
        raise NotImplementedError


_collector = StateCollector()
unique = _collector.unique
