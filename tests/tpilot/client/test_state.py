import pytest
import unittest
import mock
'''
from pilot.client.state import (_State, DisjointState, as_status)
from pilot.client.transform import (Transform, TransformCase, transform_case)


class DivideByTwoState(DisjointState):
    @as_status
    def odd(number):
        return number % 2 == 1

    @as_status
    def even(number):
        return number % 2 == 0


class DivideByTwoStateByUnitTest(DisjointState):
    @as_status
    def odd(number, *, checker):
        checker.assertEqual(number % 2, 1)

    @as_status
    def even(number, *, checker):
        checker.assertEqual(number % 2, 0)


class NumberCompute(Transform):
    transform_target = DivideByTwoState

    @transform_case(from_=DivideByTwoState.odd, to_=DivideByTwoState.even)
    def multiply_two(number):
        return number * 2

    @transform_case(from_=DivideByTwoState.even, to_=DivideByTwoState.odd)
    def sub_one(number):
        return number - 1


def test_state_cls_normal():
    assert issubclass(DivideByTwoState.odd, _State)
    assert DivideByTwoState.odd.__name__ == 'odd'
    assert DivideByTwoState.odd.check(1)


def test_enum_cls():
    assert DivideByTwoState.enum() == {
        DivideByTwoState.odd, DivideByTwoState.even
    }


def test_state_get_matched_state():
    assert DivideByTwoState.get_matched_state(2) == DivideByTwoState.even


class TestState(unittest.TestCase):
    def test_state_cls_unittest_successful(self):
        self.assertTrue(DivideByTwoStateByUnitTest.odd.check(1, checker=self))

    def test_state_cls_unittest_failed(self):
        self.assertFalse(DivideByTwoStateByUnitTest.even.check(1,
                                                               checker=self))


def test_transform_case_cls():
    assert issubclass(NumberCompute.multiply_two, TransformCase)
    assert NumberCompute.multiply_two.__name__ == 'multiply_two'


@pytest.mark.asyncio
async def test_transform_normal():
    even_number = await NumberCompute.multiply_two.do(1)
    assert DivideByTwoState.even.check(even_number)
    odd_number = await NumberCompute.sub_one.do(even_number)
    assert DivideByTwoState.odd.check(odd_number)


@pytest.mark.asyncio
async def test_transform_from_failed():
    with pytest.raises(AssertionError):
        await NumberCompute.multiply_two.do(2)


@pytest.mark.asyncio
async def test_transform_from_failed_but_skip_check():
    await NumberCompute.multiply_two.do(2, check_from=False)


@pytest.mark.asyncio
async def test_transform_to_failed():
    with pytest.raises(AssertionError):
        await NumberCompute.sub_one.do(3)


@pytest.mark.asyncio
async def test_transform_to_failed_but_skip_check():
    await NumberCompute.sub_one.do(3, check_from=False, check_to=False)


class TestTransform(unittest.IsolatedAsyncioTestCase):
    async def test_transform_unittest_successful(self):
        self.assertEqual(await NumberCompute.multiply_two.do(1, checker=self),
                         2)

    async def test_transform_unittest_failed(self):
        with self.assertRaises(AssertionError):
            await NumberCompute.multiply_two.do(2, checker=self)


async def test_refresh():
    m = mock.Mock(return_value=None)
    NumberCompute.multiply_two.refresh_cache(m)
    NumberCompute.multiply_two.do(1)
    m.assret_called_once()
import math

from pilot.client import state as pstate


class NumberStateGroup(pstate.StateGroup):
    sign_state = pstate.SubstateGroup(disjoint=True)
    decimal_state = pstate.SubstateGroup(disjoint=True)

    @sign_state.add
    def positive(self, target):
        self._checker.aseertGreater(target, 0)

    @sign_state
    def zero(self, target):
        self._checker.assertEqual(target, 0)

    @sign_state.add
    def negative(self, target):
        self._checker.assertLess(target, 0)

    @decimal_state.add
    def integer(self, target):
        self._assertEqual(math.floor(target), target)

    @integer.add
    def even(self, target):
        self._assertEqual(target % 2, 0)

    @integer.add
    def odd(self, target):
        return not self.even(target)

    @decimal_state.add
    def float(self, target):
        return not self.integer(target)

'''
