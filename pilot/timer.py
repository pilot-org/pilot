import logging
import functools
import datetime
import contextlib
import time

from typing import Optional
from collections.abc import Callable


def _get_logger(category: Optional[str]):
    logger_name = __name__
    logger_name += '' if category is None else f'.{category}'
    return logging.getLogger(logger_name)


@contextlib.contextmanager
def _log_time_spent(category: Optional[str], name: str):
    start_time = datetime.datetime.now()
    start_click = time.perf_counter()
    yield
    end_click = time.perf_counter()
    end_time = datetime.datetime.now()

    _get_logger(category).info(
        f'{name} spent {end_time - start_time}s with sleep, {end_click-start_click}s without sleep'
    )


@contextlib.contextmanager
def log_time_spent_ctx(category: Optional[str]):
    with _log_time_spent(category, 'By with'):
        yield


@functools.singledispatch
def log_time_spent(arg):
    return arg


@log_time_spent.register
def _with_category(arg: str) -> Callable:
    category = arg

    def wrap_with_category(func: Callable):
        @functools.wraps(func)
        def wrap(*args, **kwargs):
            with _log_time_spent(category, func.__name__):
                return func(*args, **kwargs)

        return wrap

    return wrap_with_category


@log_time_spent.register
def _witout_category(arg: Callable) -> Callable:
    func = arg

    @functools.wraps(func)
    def wrap(*args, **kwargs):
        with _log_time_spent(None, func.__name__):
            return func(*args, **kwargs)

    return wrap
