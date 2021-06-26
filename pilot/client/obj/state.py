import enum
import asyncio
import asyncclick as click
from loguru import logger


class _StateOperatorEnum(enum.Enum):
    AND = '&'
    OR = '|'
    NONE = enum.auto()


def _merge(self, operator, other):
    if isinstance(self, _UniqueState) and isinstance(other, _UniqueState):
        return _MergeState(operator, {self.unique_id, other.unique_id},
                           self._collector)
    elif isinstance(self, _UniqueState) and isinstance(other, _MergeState):
        new_ids = set(other.ids)
        new_ids.add(self.unique_id)
        return _MergeState(other.operator, new_ids, self._collector)
    elif isinstance(self, _MergeState) and isinstance(other, _UniqueState):
        new_ids = set(self.ids)
        new_ids.add(other.unique_id)
        return _MergeState(self.operator, new_ids, self._collector)
    elif isinstance(self, _MergeState) and isinstance(other, _MergeState):
        if self.operator == other.operator and self.operator == operator:
            new_ids = set(self.ids)
            new_ids.union(other.ids)
            return _MergeState(self.operator, new_ids, self._collector)
        return _MergeState(operator, {self, other}, self._collector)
    elif isinstance(self, StateEnum):
        return _merge(self.value, operator, other)
    elif isinstance(other, StateEnum):
        return _merge(self, operator, other.value)
    raise click.UsageError(f'{other} must be _UniqueState or _MergeState')


class _State:
    def __init__(self, collector):
        self._collector = collector

    def __repr__(self):
        return f'{self._enum_obj.__class__.__name__}.{self._enum_obj.name}({self.expression})'

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

    def precheck(self, check_target):
        self._enum_obj.precheck(check_target)


def _first(obj):
    if isinstance(obj, _MergeState):
        return _first(obj._ids[0])
    if isinstance(obj, _UniqueState):
        return obj._unique_id
    return obj


class _MergeState(_State):
    def __init__(self, operator, ids, collector):
        super().__init__(collector)
        self._operator = operator
        self._ids = sorted(ids, key=_first)

    @property
    def expression(self):
        expressions = []
        for i in self._ids:
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

    async def check(self, check_target):
        self.precheck(check_target)
        tasks = []
        for i in self._ids:
            if isinstance(i, int):
                state = self._collector.get_unique_state(i)
                tasks.append(state.check(check_target))
            elif isinstance(i, _MergeState):
                tasks.append(i.check(check_target))
            else:
                raise click.UsageError(f'Unknown type: {type(i)}')
        results = await asyncio.gather(*tasks)
        if self._operator == _StateOperatorEnum.AND:
            return all(results)
        elif self._operator == _StateOperatorEnum.OR:
            return any(results)
        raise click.UsageError(f'Unknown operator: {self._operator}')


class _UniqueState(_State):
    def __init__(self, unique_id, collector):
        super().__init__(collector)
        self._unique_id = unique_id

    @property
    def expression(self):
        return str(self._unique_id)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            value = other
        elif isinstance(other, StateEnum):
            value = other.value
        else:
            return False
        return self._unique_id == value._unique_id

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def operator(self):
        return _StateOperatorEnum.NONE

    async def check(self, check_target):
        self.precheck(check_target)
        state = await self._enum_obj._get_unique_state(check_target)
        res = state == self
        logger.debug('{}(result) {} {}(expected)', state, '=' if res else '!=',
                     self)
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
        self._unique_state_map[unique_id] = value
        return value

    def get_unique_state(self, unique_id):
        return self._unique_state_map[unique_id]

    def register_enum(self, enum_cls):
        self._state_enum_group.add(enum_cls)


class StateEnum(_State, enum.Enum):
    def __init__(self, value):
        value.set_enum_obj(self)

    def __repr__(self):
        return self.value.__repr__()

    @classmethod
    async def matched_unique_states(cls, check_target):
        cls.precheck(check_target)
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

    @classmethod
    def precheck(cls, check_target):
        if cls._can_check(check_target) is False:
            raise click.UsageError(
                f'Type ({type(check_target)} of {check_target} is not matched')

    @classmethod
    def _can_check(cls, check_target):
        raise NotImplementedError

    @classmethod
    async def _get_unique_state(self, check_target):
        raise NotImplementedError


_collector = StateCollector()
unique = _collector.unique
