import pytest
from loguru import logger

from pilot.client.obj import state as pstate
from pilot.client.obj.error import ObjUsage

_collector = pstate.StateCollector()
unique = _collector.unique


class ABCStateEnum(pstate.StateEnum):
    A = unique()
    B = unique()
    C = unique()
    I = unique()
    J = unique()
    K = unique()
    X = unique()
    Y = unique()
    Z = unique()
    AB = A & B
    ABC = A & B & C
    IJ = I | J
    IJK = I | J | K
    XY = X & Y
    XYZ = XY & Z
    MIX1 = (A & I) | (B & J)
    MIX2 = (B & J) | (A & I)
    MIX3 = (A | I) & (B | J)


@pytest.mark.parametrize('enum_obj,string', [
    (ABCStateEnum.A, '<State ABCStateEnum.A(0)>'),
    (ABCStateEnum.AB, '<State ABCStateEnum.AB(0 & 1)>'),
    (ABCStateEnum.ABC, '<State ABCStateEnum.ABC(0 & 1 & 2)>'),
    (ABCStateEnum.IJ, '<State ABCStateEnum.IJ(3 | 4)>'),
    (ABCStateEnum.IJK, '<State ABCStateEnum.IJK(3 | 4 | 5)>'),
    (ABCStateEnum.XYZ, '<State ABCStateEnum.XYZ(6 & 7 & 8)>'),
    (ABCStateEnum.MIX1, '<State ABCStateEnum.MIX1((0 & 3) | (1 & 4))>'),
    (ABCStateEnum.MIX2, '<State ABCStateEnum.MIX2((0 & 3) | (1 & 4))>'),
    (ABCStateEnum.MIX3, '<State ABCStateEnum.MIX3((0 | 3) & (1 | 4))>'),
])
def test_state_str(enum_obj, string):
    assert str(enum_obj.value) == string


def test_enum_value_equal():
    assert ABCStateEnum.A.value == ABCStateEnum.A
    assert ABCStateEnum.A == ABCStateEnum.A.value


def test_state_name():
    assert str(ABCStateEnum.A) == 'ABCStateEnum.A'
    assert str(ABCStateEnum.AB) == 'ABCStateEnum.AB'
    assert str(ABCStateEnum.ABC) == 'ABCStateEnum.ABC'


class IntegerStateEnum(pstate.StateEnum):
    odd = unique()
    even = unique()

    @classmethod
    def _get_target_obj_type(cls):
        return int

    @classmethod
    async def _get_unique_state(cls, i):
        return cls.odd if i % 2 == 1 else cls.even


class Mod3StateEnum(pstate.StateEnum):
    zero = unique()
    one = unique()
    two = unique()
    not_divide = one | two

    @classmethod
    def _get_target_obj_type(cls):
        return int

    @classmethod
    async def _get_unique_state(cls, i):
        i = i % 3
        if i == 0:
            return cls.zero
        if i == 1:
            return cls.one
        return cls.two


@pytest.mark.asyncio
async def test_state_get_unique():
    assert Mod3StateEnum.zero in await Mod3StateEnum.matched_unique_states(15)


@pytest.mark.asyncio
async def test_state_check_normal():
    assert await Mod3StateEnum.one.check(4)
    assert await Mod3StateEnum.two.value.check(5)
    assert await Mod3StateEnum.not_divide.check(7)


@pytest.mark.asyncio
async def test_state_check_type_not_match():
    with pytest.raises(ObjUsage):
        await Mod3StateEnum.two.check('17')


class FactorStateEnum(pstate.StateEnum):
    factor2 = unique()
    factor3 = unique()
    factor5 = unique()
    factor7 = unique()
    neither = unique()

    # TODO:
    factor6 = factor2 & factor3
    factor10 = factor2 & factor5

    @classmethod
    def _get_target_obj_type(cls):
        return int

    @classmethod
    async def _get_unique_state(cls, i):
        if i % 2 == 0:
            return cls.factor2
        if i % 3 == 0:
            return cls.factor3
        if i % 5 == 0:
            return cls.factor5
        if i % 7 == 0:
            return cls.factor7


class MixStateEnum(pstate.StateEnum):
    MIX0 = Mod3StateEnum.one
    MIX1 = Mod3StateEnum.one & FactorStateEnum.factor2
    MIX2 = Mod3StateEnum.two & FactorStateEnum.factor5
    MIX3 = MIX1 | MIX2

    @classmethod
    def _get_target_obj_type(cls):
        return int


@pytest.mark.asyncio
async def test_state_check_merge():
    assert await MixStateEnum.MIX1.check(4)
    assert not await MixStateEnum.MIX1.check(6)
    assert await MixStateEnum.MIX2.check(5)
    assert not await MixStateEnum.MIX2.check(10)
    assert await MixStateEnum.MIX3.check(4)


class RAIDState(pstate.StateEnum):
    NORMAL = unique()
    DEGRADED = unique()
    CRASHED = unique()


class LoadedState(pstate.StateEnum):
    LOADED = pstate.unique()
    NOT_LOADED = pstate.unique()


class CacheState(pstate.StateEnum):
    CRASHED = RAIDState.CRASHED | LoadedState.NOT_LOADED


@pytest.mark.asyncio
async def test_state_proxy():
    class A:
        def __init__(self, i) -> None:
            self.i = i

    class IntStateEnum(pstate.StateEnum):
        one = unique()
        two = unique()
        other = unique()

        @classmethod
        def _get_target_obj_type(cls):
            return int

        @classmethod
        async def _get_unique_state(cls, i):
            if i == 1:
                return cls.one
            elif i == 2:
                return cls.two
            return cls.other

    class IntV2StateEnum(pstate.StateEnum):
        one = IntStateEnum.one
        two = IntStateEnum.two
        other = IntStateEnum.other

        @classmethod
        def _get_target_obj_type(cls):
            return int

    assert await IntV2StateEnum.one.check(1)
    assert await IntV2StateEnum.two.check(2)

    def get_int_from_A(a):
        return a.i

    class AStateEnum(pstate.StateEnum):
        one = IntStateEnum.one.for_another_obj(get_int_from_A)
        two = IntStateEnum.two.for_another_obj(get_int_from_A)

        @classmethod
        def _get_target_obj_type(cls):
            return A

    a1 = A(1)
    a2 = A(2)

    assert await AStateEnum.one.check(a1)
    assert await AStateEnum.two.check(a2)

    with pytest.raises(ObjUsage):

        class IntVdStateEnum(pstate.StateEnum):
            one = IntStateEnum.one
            two = IntStateEnum.two
            other = IntStateEnum.other

            @classmethod
            def _get_target_obj_type(cls):
                return float


@pytest.mark.asyncio
async def test_state_proxy_mixin():
    class A:
        def __init__(self, i: int) -> None:
            self.i = i

    class B:
        def __init__(self, a, s: str) -> None:
            self.a = a
            self.s = s

    class IntStateEnum(pstate.StateEnum):
        one = unique()
        two = unique()
        other = unique()

        @classmethod
        def _get_target_obj_type(cls):
            return int

        @classmethod
        async def _get_unique_state(cls, i):
            if i == 1:
                return cls.one
            elif i == 2:
                return cls.two
            return cls.other

    class StrStateEnum(pstate.StateEnum):
        one = unique()
        two = unique()
        other = unique()

        @classmethod
        def _get_target_obj_type(cls):
            return str

        @classmethod
        async def _get_unique_state(cls, i):
            if i == '1':
                return cls.one
            elif i == '2':
                return cls.two
            return cls.other

    def get_i_from_a(a):
        return a.i

    class AStateEnum(pstate.StateEnum):
        one = IntStateEnum.one.for_another_obj(get_i_from_a)
        two = IntStateEnum.two.for_another_obj(get_i_from_a)

        @classmethod
        def _get_target_obj_type(cls):
            return A

    def get_a_from_b(b):
        return b.a

    class BBaseStateEnum(pstate.StateEnum):
        @classmethod
        def _get_target_obj_type(cls):
            return B

    class AinBStateEnum(BBaseStateEnum):
        one = AStateEnum.one.for_another_obj(get_a_from_b)
        two = AStateEnum.two.for_another_obj(get_a_from_b)

    def get_str_from_b(b):
        return b.s

    class StrInBStateEnum(BBaseStateEnum):
        one = StrStateEnum.one.for_another_obj(get_str_from_b)
        two = StrStateEnum.two.for_another_obj(get_str_from_b)

    class BStateEnum(BBaseStateEnum):
        one_one = AinBStateEnum.one & StrInBStateEnum.one
        one_two = AinBStateEnum.one & StrInBStateEnum.two
        two_one = AinBStateEnum.two & StrInBStateEnum.one
        two_two = AinBStateEnum.two & StrInBStateEnum.two
        one_one_v2 = AStateEnum.one.for_another_obj(
            get_a_from_b) & StrStateEnum.one.for_another_obj(get_str_from_b)
        one_two_v2 = AStateEnum.one.for_another_obj(
            get_a_from_b) & StrStateEnum.two.for_another_obj(get_str_from_b)
        two_one_v2 = AStateEnum.two.for_another_obj(
            get_a_from_b) & StrStateEnum.one.for_another_obj(get_str_from_b)
        two_two_v2 = AStateEnum.two.for_another_obj(
            get_a_from_b) & StrStateEnum.two.for_another_obj(get_str_from_b)

    assert await BStateEnum.one_one.check(B(A(1), '1'))
    assert await BStateEnum.one_two.check(B(A(1), '2'))
    assert await BStateEnum.two_one.check(B(A(2), '1'))
    assert await BStateEnum.two_two.check(B(A(2), '2'))
    assert await BStateEnum.one_one_v2.check(B(A(1), '1'))
    assert await BStateEnum.one_two_v2.check(B(A(1), '2'))
    assert await BStateEnum.two_one_v2.check(B(A(2), '1'))
    assert await BStateEnum.two_two_v2.check(B(A(2), '2'))
