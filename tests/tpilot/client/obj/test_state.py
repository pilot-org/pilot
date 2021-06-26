import pytest
import asyncclick as click

from pilot.client.obj import state as pstate


class ABCStateEnum(pstate.StateEnum):
    A = pstate.unique()
    B = pstate.unique()
    C = pstate.unique()
    I = pstate.unique()
    J = pstate.unique()
    K = pstate.unique()
    X = pstate.unique()
    Y = pstate.unique()
    Z = pstate.unique()
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
    (ABCStateEnum.A, 'ABCStateEnum.A(0)'),
    (ABCStateEnum.AB, 'ABCStateEnum.AB(0 & 1)'),
    (ABCStateEnum.ABC, 'ABCStateEnum.ABC(0 & 1 & 2)'),
    (ABCStateEnum.IJ, 'ABCStateEnum.IJ(3 | 4)'),
    (ABCStateEnum.IJK, 'ABCStateEnum.IJK(3 | 4 | 5)'),
    (ABCStateEnum.XYZ, 'ABCStateEnum.XYZ(6 & 7 & 8)'),
    (ABCStateEnum.MIX1, 'ABCStateEnum.MIX1((0 & 3) | (1 & 4))'),
    (ABCStateEnum.MIX2, 'ABCStateEnum.MIX2((0 & 3) | (1 & 4))'),
    (ABCStateEnum.MIX3, 'ABCStateEnum.MIX3((0 | 3) & (1 | 4))'),
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
    odd = pstate.unique()
    even = pstate.unique()

    @classmethod
    def _can_check(cls, i):
        return isinstance(i, int)

    @classmethod
    async def _get_unique_state(cls, i):
        return cls.odd if i % 2 == 1 else cls.even


class Mod3StateEnum(pstate.StateEnum):
    zero = pstate.unique()
    one = pstate.unique()
    two = pstate.unique()
    not_divide = one | two

    @classmethod
    def _can_check(cls, i):
        return isinstance(i, int)

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
    with pytest.raises(click.UsageError):
        await Mod3StateEnum.two.check('17')


class FactorStateEnum(pstate.StateEnum):
    factor2 = pstate.unique()
    factor3 = pstate.unique()
    factor5 = pstate.unique()
    factor7 = pstate.unique()
    neither = pstate.unique()

    # TODO:
    factor6 = factor2 & factor3
    factor10 = factor2 & factor5

    @classmethod
    def _can_check(cls, i):
        return isinstance(i, int)

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
    MIX1 = Mod3StateEnum.one & FactorStateEnum.factor2
    MIX2 = Mod3StateEnum.two & FactorStateEnum.factor5
    MIX3 = MIX1 | MIX2

    @classmethod
    def _can_check(cls, i):
        return isinstance(i, int)


@pytest.mark.asyncio
async def test_state_check_merge():
    assert await MixStateEnum.MIX1.check(4)
    assert not await MixStateEnum.MIX1.check(6)
    assert await MixStateEnum.MIX2.check(5)
    assert not await MixStateEnum.MIX2.check(10)
    assert await MixStateEnum.MIX3.check(4)


class RAIDState(pstate.StateEnum):
    NORMAL = pstate.unique()
    DEGRADED = pstate.unique()
    CRASHED = pstate.unique()

class LoadedState(pstate.StateEnum):
    LOADED = pstate.unique()
    NOT_LOADED = pstate.unique()

class CacheState(pstate.StateEnum):
    CRASHED = RAIDState.CRASHED | LoadedState.NOT_LOADED
