import pytest
from .fixture import (
    writer,
    urulogs,
)

pytest_plugins = ["docker_compose"]
# sometime can't remove container, please use 'sudo aa-remove-unknown' to fix it
