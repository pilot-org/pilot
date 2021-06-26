import unittest

from pilot import timer


class TestTimer(unittest.TestCase):
    args = (1, 'a')
    kwargs = {'a': 1, 'b': 'c'}

    def test_with_ctx(self):
        category = 'test_ctx'
        with self.assertLogs(f'pilot.timer.{category}', level='INFO') as cm:
            with timer.log_time_spent_ctx(category):
                pass
        self.assertRegex(cm.output[0],
                         f'INFO:pilot.timer.{category}:By with spent')

    def test_without_category(self):
        @timer.log_time_spent
        def t(*args, **kwargs):
            return args, kwargs

        with self.assertLogs('pilot.timer', level='INFO') as cm:
            args, kwargs = t(*self.args, **self.kwargs)
            self.assertTupleEqual(args, self.args)
            self.assertDictEqual(kwargs, self.kwargs)

    def test_with_category(self):
        category = 'test_func'

        @timer.log_time_spent(category)
        def t(*args, **kwargs):
            return args, kwargs

        with self.assertLogs(f'pilot.timer.{category}', level='INFO') as cm:
            args, kwargs = t(*self.args, **self.kwargs)
            self.assertTupleEqual(args, self.args)
            self.assertDictEqual(kwargs, self.kwargs)