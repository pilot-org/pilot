import unittest
import functools
import contextlib
import io


class FunctionTestCase(unittest.FunctionTestCase):
    def runTest(self):
        self._testFunc(self)


def run_with_unittest(task, **kwargs):
    '''
    Pass TestCase as the first param, so can use self.assert, ... so on
    e.g.
    def test(self):
        self.assertEqual(1, 2)
    run_with_unittest(test)
    '''
    suite = unittest.TestSuite()
    suite.addTest(FunctionTestCase(task, **kwargs))
    unittest.TextTestRunner().run(suite)


class Checker:
    def __init__(self, tester=None):
        self._tester = tester

    def __getattr__(self, key):
        if key.startswith('assert'):

            if self._tester is None:

                def assert_something(*args, **kwargs):
                    def test(checker):
                        assert_func = getattr(checker, key)
                        assert_func(*args, **kwargs)

                    run_with_unittest(test)

                return staticmethod(assert_something)
            else:
                return getattr(self._tester, key)


class _FunctionTestCase(unittest.FunctionTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._checker = Checker(self)

    def runTest(self):
        kwargs = dict(self._kwargs)
        kwargs['checker'] = self._checker
        self._res = None
        res = self._testFunc(*self._args, **kwargs)
        self._res = res

    def get_checker(self):
        return self._checker

    def get_return(self):
        return self._res

    def get_result(self):
        return self._test_result

    def get_msg(self):
        return self._msg

    def check(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        with io.StringIO() as buf:
            with contextlib.redirect_stderr(buf):
                runner = unittest.TextTestRunner(verbosity=1, tb_locals=True)
                self._test_result = runner.run(self)
            self._msg = buf.getvalue()
            return self._test_result


class CheckerManager:
    def __init__(self):
        self._checker_map_testcase = {}
        self._wrapped_func_map_testcase = {}
        self._wrapper_func_map_testcase = {}

    def pass_checker(self, raw_func):
        def wrapper(*args, **kwargs):
            testcase = _FunctionTestCase(raw_func)
            self._wrapper_func_map_testcase[wrapper] = testcase
            self._wrapped_func_map_testcase[raw_func] = testcase
            self._checker_map_testcase[testcase.get_checker()] = testcase
            testcase.check(*args, **kwargs)
            return testcase.get_return()

        return functools.update_wrapper(wrapper, raw_func)

    def get_testcase(self, target):
        if isinstance(target, Checker):
            return self._checker_map_testcase[target]
        testcase = self._wrapper_func_map_testcase.get(target)
        if testcase is not None:
            return testcase
        testcase = self._wrapped_func_map_testcase.get(target)
        if testcase is not None:
            return testcase


_manager = CheckerManager()
pass_checker = _manager.pass_checker
get_testcase = _manager.get_testcase