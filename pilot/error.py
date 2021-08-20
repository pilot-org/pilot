import contextlib
import sys
import traceback
import functools
import asyncio
import traceback
import inspect
import asyncclick as click
from loguru import logger


class ErrorCollector(object):
    def __init__(self, target, prepare_try_func):
        self._target = target
        self._prepare_try_func = prepare_try_func
        self._errors = []
        self._collect_running = True

    @property
    def errors(self):
        return self._errors

    def stop_collect(self):
        self._collect_running = False

    def add_error(self, err):
        self._errors.append(err)

    def __getattr__(self, key):
        func = getattr(self._target, key)
        if not self._collect_running:
            return func
        return self._prepare_try_func(func, self)


class MergedErrors(Exception):
    def __init__(self, errors):
        self._errors = errors

    @property
    def errors(self):
        return self._errors

    def raise_if_error(self):
        if self._errors:
            for err in self._errors:
                exctype, value, tb = err
                tb_e = traceback.TracebackException(exctype, value, tb)
                msg_lines = list(tb_e.format())
                click.echo(''.join(msg_lines), err=True)
            raise self


@contextlib.contextmanager
def merge_error(target, do_raise=True):
    def prepare_try_func(func, collector):
        def try_func(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except:
                collector.add_error(sys.exc_info())

        return try_func

    collector = ErrorCollector(target, prepare_try_func)
    yield collector
    collector.stop_collect()
    if do_raise:
        d = MergedErrors(collector.errors)
        d.raise_if_error()


@contextlib.contextmanager
def treat_as_subTest(testcase):
    def prepare_try_func(func, collector):
        def try_func(*args, **kwargs):
            with testcase.subTest(args=args, kwargs=kwargs):
                return func(*args, **kwargs)

        return try_func

    collector = ErrorCollector(testcase, prepare_try_func)
    yield collector
    collector.stop_collect()


class NeedRetryError(Exception):
    def __init__(self, info):
        self._info = info

    @property
    def exc_info(self):
        return self._info


@contextlib.contextmanager
def want_to_retry():
    try:
        yield
    except Exception as e:
        raise NeedRetryError(sys.exc_info())


@contextlib.contextmanager
def treat_as_need_retry(target, change_to_need_retry_exceptions=Exception):
    def prepare_need_retry(func, collector):
        def need_retry(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except change_to_need_retry_exceptions:
                collector.add_error(sys.exc_info())

        return need_retry

    collector = ErrorCollector(target, prepare_need_retry)
    yield collector
    collector.stop_collect()
    if collector.errors:
        raise NeedRetryError(collector.errors[0])


def retry(exception=Exception, max_get=3, interval=0, when_retry_it=None):
    if callable(exception) and (not inspect.isclass(exception)
                                or not issubclass(exception, Exception)):
        return retry()(exception)
    if not isinstance(exception, (list, tuple)):
        exception = (exception, )

    def wrapper(raw_func):

        is_async_func = asyncio.iscoroutinefunction(raw_func)

        async def new_async_func(*args, **kwargs):
            nonlocal max_get
            nonlocal interval
            max_get = kwargs.pop('max_get', max_get)
            interval = kwargs.pop('interval', interval)
            for i in range(max_get):
                if i == max_get - 1:
                    cm = contextlib.nullcontext()
                else:
                    cm = contextlib.suppress(*exception)
                with cm:
                    res = raw_func(*args, **kwargs)
                    if is_async_func:
                        res = await res
                    return res
                logger.debug(
                    'Failed to call {}(*{}, **{}) at {} of {}, retry it',
                    raw_func.__name__, args, kwargs, i + 1, max_get)
                if when_retry_it is not None and callable(when_retry_it):
                    when_retry_it()
                if interval > 0:
                    await asyncio.sleep(interval)

        if is_async_func:
            return functools.update_wrapper(new_async_func, raw_func)
        else:

            def new_func(*args, **kwargs):
                return asyncio.run(new_async_func(*args, **kwargs))

            return functools.update_wrapper(new_func, raw_func)

    return wrapper


def can_retry(exception, *args, **kwargs):
    if callable(exception) and (not inspect.isclass(exception)
                                or not issubclass(exception, Exception)):
        return retry(max_get=1)(exception)
    if 'max_get' not in kwargs:
        kwargs['max_get'] = 1
    return retry(exception, *args, **kwargs)


def logger_exception(etype, value, tb):
    for info in traceback.format_exception(etype, value, tb):
        for line in info.split('\n'):
            if line == '':
                continue
            logger.error('{}', line)
