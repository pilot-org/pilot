import pytest
from loguru import logger


@pytest.fixture
def writer():
    class w:
        def __init__(self):
            self._written = []

        def read(self):
            return ''.join(self._written)

        @property
        def output(self):
            return self.read().split('\n')[0:-1]

        def clear(self):
            self._written.clear()

        def __call__(self, message):
            self._written.append(message)

    return w()


@pytest.fixture
def urulogs(writer, request):
    marker = request.node.get_closest_marker('urulogs')
    if marker is None:
        raise RuntimeError(
            f'Please pass param by "@pytest.mark.urulogs(\'a.b.c\', level=\'DEBUG\')"'
        )

    target = marker.args[0]
    level = marker.kwargs.get('level', 'DEBUG')
    tmp = logger.add(writer,
                     format='{level}:{name}:{message}',
                     filter=target,
                     level=level)
    yield writer
    logger.complete()
    logger.remove(tmp)
