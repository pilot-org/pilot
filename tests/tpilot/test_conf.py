import pytest
import mock
import dataclasses
import asyncclick as click
from omegaconf import OmegaConf
from typing import (
    Optional,
    List,
    Tuple,
    Dict,
    TypeVar,
)

from pilot import conf as pconf
from pilot.client import connector as pconn


class _T:
    _t = mock.MagicMock()


_t = mock.MagicMock()


def test_import_class():
    assert pconf._import('tests.tpilot.test_conf', '_T') == _T


def test_import_class_failed():
    with pytest.raises(click.UsageError):
        assert pconf._import('tests.tpilot.test_conf', 'T')


def test_import_class_attr_failed():
    with pytest.raises(click.UsageError):
        assert pconf._import('tests.tpilot.test_conf', '_T', 't')


def test_import_class_attr():
    assert pconf._import('tests.tpilot.test_conf', '_T', '_t') == _T._t


def test_import_connector():
    assert pconf._import('pilot.client.connector',
                         'AsyncsshAgent') == pconn.AsyncsshAgent


def testex_import_by_yaml():
    out = OmegaConf.create(
        'cls: ${import:pilot.client.connector,AsyncsshAgent}')
    assert out.cls == pconn.AsyncsshAgent


@dataclasses.dataclass
class AllType():
    a: int
    b: str
    c: float
    d: bytes
    e: bool
    f: List[int]
    g: Optional[int]
    h: Optional[int]
    i: Optional[str]
    j: Optional[str] = None
    k: List[int] = dataclasses.field(default_factory=list)
    l: Tuple[int, ...] = dataclasses.field(default_factory=tuple)
    m: Dict[str, int] = dataclasses.field(default_factory=dict)


def test_dataclass_convert_type():
    data = pconf.dataclass_from_dict(AllType, {
        'a': 1,
        'b': 'x',
        'c': 1.5,
        'd': b'b',
        'e': True,
        'f': [1],
        'g': None,
        'h': '2',
        'i': None,
    },
                                     convert_failed_continue=False)
    assert data == AllType(a=1,
                           b='x',
                           c=1.5,
                           d=b'b',
                           e=True,
                           f=[1],
                           g=None,
                           h=2,
                           i=None,
                           j=None,
                           k=[],
                           l=tuple([]),
                           m={})


@dataclasses.dataclass
class A:
    i: int
    s: str


@dataclasses.dataclass
class B:
    i: int
    s: str


@dataclasses.dataclass
class C:
    a: A
    b: B


def test_dataclass_recursive_convert():
    data = pconf.dataclass_from_dict(C, {
        'a': {
            'i': 1,
            's': 's'
        },
        'b': {
            'i': 2,
            's': 't'
        }
    })
    assert data == C(a=A(i=1, s='s'), b=B(i=2, s='t'))


def test_dataclass_convert_handle():
    data = pconf.dataclass_from_dict(A, {'i': '1', 's': 2})
    assert data == A(i=1, s='2')


def test_dataclass_convert_failed():
    with pytest.raises(TypeError):
        pconf.dataclass_from_dict(A, {
            'i': 'zz',
            's': 'xx'
        },
                                  convert_failed_continue=False)


@pytest.mark.urulogs('pilot.conf')
def test_dataclass_convert_warning(urulogs):
    data = pconf.dataclass_from_dict(A, {'i': 'zz', 's': 'xx'})
    assert data == A(i='zz', s='xx')
    assert urulogs.output == [
        'WARNING:pilot.conf:Failed to convert zz(type: <class \'str\'>) to <class \'int\'> type, so no convert it, because invalid literal for int() with base 10: \'zz\''
    ]


@dataclasses.dataclass
class BoolData():
    b: bool


@pytest.mark.parametrize('raw,expected', [
    (True, True),
    (1, True),
    ('1', True),
    ('TRue', True),
    (b'trUe', True),
    (False, False),
    (0, False),
    ('0', False),
    ('False', False),
    (b'false', False),
])
def test_dataclass_convert_bool(raw, expected):
    data = pconf.dataclass_from_dict(BoolData, {'b': raw})
    assert data == BoolData(b=expected)


@pytest.mark.parametrize('raw,expected', [
    ('3B', 3),
    ('4 b', 4),
    ('10K', 10 * 2**10),
    ('5MB', 5 * 2**20),
    ('3.14G', 3.14 * 2**30),
    ('10000TB', 10000 * 2**40),
])
def test_parse_size(raw, expected):
    assert pconf.parse_size(raw) == int(expected)
