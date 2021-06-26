import pytest
import unittest
import mock
import io
import contextlib

from pilot import error as perror


class _T(object):
    def __init__(self):
        self._accumlate = 0

    def test1(self):
        raise ValueError('test1 error')

    def test2(self):
        raise KeyError('test2 error')

    def test3(self, target):
        self._accumlate += 1
        if self._accumlate < target:
            raise RuntimeError


class _TestTreatAsSubTest(unittest.TestCase):
    def _test_treat_as_subTest(self):
        with perror.treat_as_subTest(self) as m:
            m.assertEqual(1, 2)
            m.assertEqual(1, 3)


class TestErrorCollector(unittest.TestCase):
    def test_merge_error(self):
        t = _T()
        with io.StringIO() as buf:
            with contextlib.redirect_stderr(buf):
                with self.assertRaises(perror.MergedErrors) as cm:
                    with perror.merge_error(t) as m:
                        m.test1()
                        m.test2()
            pattern = 'Traceback \(most recent call last\):([^\n]*\n){1,10}ValueError: test1 error'
            pattern += '\n\n'
            pattern += 'Traceback \(most recent call last\):([^\n]*\n){1,10}KeyError: \'test2 error\''
            self.assertRegex(buf.getvalue(), pattern)

        the_exception = cm.exception

        e = the_exception.errors[0]
        self.assertEqual(e[0], ValueError)
        self.assertEqual(e[1].args, ('test1 error', ))

        e = the_exception.errors[1]
        self.assertEqual(e[0], KeyError)
        self.assertEqual(e[1].args, ('test2 error', ))

    def test_treat_as_subTest(self):
        pattern = 'Traceback \(most recent call last\):([^\n]*\n){1,10}AssertionError: 1 != 2'
        pattern += '\n([^\n]*\n){1,4}'
        pattern += 'Traceback \(most recent call last\):([^\n]*\n){1,10}AssertionError: 1 != 3'
        suite = unittest.TestLoader().loadTestsFromName(
            'tpilot.test_error._TestTreatAsSubTest._test_treat_as_subTest')
        with io.StringIO() as buf:
            runner = unittest.TextTestRunner(stream=buf)
            runner.run(suite)
            self.assertRegex(buf.getvalue(), pattern)


class TestTreatAsNeedRetry(unittest.TestCase):
    def test_general(self):
        t = _T()
        while True:
            try:
                with perror.treat_as_need_retry(t) as m:
                    m.test3(10)
                    break
            except perror.NeedRetryError:
                pass


def test_retry_normal():
    m = mock.MagicMock(side_effect=[RuntimeError, 1])

    @perror.retry(RuntimeError, 2, 0)
    def t():
        return m()

    assert t() == 1
    assert m.call_count == 2


@pytest.mark.asyncio
async def test_retry_normal_async():
    m = mock.MagicMock(side_effect=[RuntimeError, 1])

    @perror.retry(RuntimeError, 2, 0)
    async def t():
        return m()

    assert await t() == 1
    assert m.call_count == 2


def test_retry_handle_muitple_except():
    m = mock.MagicMock(side_effect=[RuntimeError, KeyError, 1])

    @perror.retry((RuntimeError, KeyError), 3, 0)
    def t():
        return m()

    assert t() == 1
    assert m.call_count == 3


def test_retry_failed():
    m = mock.MagicMock(side_effect=[RuntimeError, RuntimeError])

    @perror.retry(RuntimeError, 2, 0)
    def t():
        return m()

    with pytest.raises(RuntimeError):
        t()
    assert m.call_count == 2


def test_retry_non_handle_type():
    m = mock.MagicMock(side_effect=RuntimeError)

    @perror.retry(KeyError, 2, 0)
    def t():
        return m()

    with pytest.raises(RuntimeError):
        t()
    assert m.call_count == 1


def test_retry_arg():
    @perror.retry(RuntimeError, 2, 0)
    def t(*args, **kwargs):
        assert args == (1, 2)
        assert kwargs == {'a': 1}
        return 1

    assert t(1, 2, a=1) == 1


@pytest.mark.urulogs('pilot.error')
def test_retry_msg(urulogs):
    m = mock.MagicMock(side_effect=[RuntimeError, RuntimeError, 1])

    @perror.retry(RuntimeError, 3, 0)
    def t():
        return m()

    t()
    assert urulogs.output == [
        'DEBUG:pilot.error:Failed to call t(*(), **{}) at 1 of 3, retry it',
        'DEBUG:pilot.error:Failed to call t(*(), **{}) at 2 of 3, retry it',
    ]


def test_retry_origin_config():
    m = mock.MagicMock(side_effect=[RuntimeError, RuntimeError, 1])

    @perror.retry
    def t():
        return m()

    t()
    assert m.call_count == 3


@mock.patch('asyncio.sleep')
def test_retry_change_arg(mock_sleep):
    m = mock.MagicMock(side_effect=RuntimeError)

    @perror.retry
    def t():
        return m()

    with pytest.raises(RuntimeError):
        t(max_get=2, interval=1)
    assert m.call_count == 2
    mock_sleep.assert_awaited_once_with(1)


def test_can_retry_normal():
    m = mock.MagicMock(side_effect=RuntimeError)

    @perror.can_retry
    def t():
        return m()

    with pytest.raises(RuntimeError):
        t(max_get=2)
    assert m.call_count == 2


def test_can_retry_normal_default():
    m = mock.MagicMock(side_effect=RuntimeError)

    @perror.can_retry
    def t():
        return m()

    with pytest.raises(RuntimeError):
        t()
    assert m.call_count == 1
