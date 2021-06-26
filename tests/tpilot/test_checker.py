import pytest
import unittest
import re

from pilot import checker as pchecker


def test_pass_checker_normal():
    @pchecker.pass_checker
    def t(*, checker):
        pass

    t()
    testcase = pchecker.get_testcase(t)
    res = testcase.get_result()
    assert isinstance(res, unittest.TextTestResult)
    assert res.wasSuccessful() == True
    #res.printErrors()
    #assert buf.getvalue() == ''


def test_pass_checker_error():
    @pchecker.pass_checker
    def t(*, checker):
        raise RuntimeError

    t()
    testcase = pchecker.get_testcase(t)
    res = testcase.get_result()
    assert res.wasSuccessful() == False
    assert re.search('raise RuntimeError', testcase.get_msg(), re.M)


def test_pass_checker_pass_obj():
    @pchecker.pass_checker
    def t(*, checker):
        return checker

    checker = t()
    assert isinstance(checker, pchecker.Checker)


def test_pass_checker_args():
    @pchecker.pass_checker
    def t(*args, checker, **kwargs):
        return args, kwargs

    args, kwargs = t(1, 2, 3, a=1, b=2)
    assert args == (1, 2, 3)
    assert kwargs == {'a': 1, 'b': 2}


def test_checker_successful():
    @pchecker.pass_checker
    def t(*, checker):
        checker.assertTrue(True)

    t()
    testcase = pchecker.get_testcase(t)
    res = testcase.get_result()
    assert res.wasSuccessful() == True


def test_checker_failed():
    @pchecker.pass_checker
    def t(*, checker):
        checker.assertTrue(False)

    t()
    testcase = pchecker.get_testcase(t)
    res = testcase.get_result()
    assert res.wasSuccessful() == False