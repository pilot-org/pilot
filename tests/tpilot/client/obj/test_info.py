import asyncio
import pytest
from loguru import logger

from pilot.client import core as pclient
from pilot.client import obj as pobj
from pilot.client import mock as pmock


class ClientBaseForTest(pclient.Client):
    async def run(self, *args, **kwargs):
        conn = await self.connect('test')
        return await conn.run(*args, **kwargs)


@pytest.mark.asyncio
async def test_get_cached_info_basic_each():
    class CachedDataInfo(pobj.CachedInfoGroupEntry):
        @pobj.cached_info(depend_on_id=False)
        async def get_by_key(self, key):
            # NOTE: first arg must be named by self
            return await self.owner.run(key)

    class ClientForTest(ClientBaseForTest):
        info = CachedDataInfo.as_property()

    data = {'a': 1, 'b': 2}

    def effect(arg):
        return data[arg]

    async with pmock.mock_client_run(ClientForTest) as it:
        it.mock_run.side_effect = effect
        assert type(it.client) == ClientForTest
        info = it.client.info
        assert type(info) == CachedDataInfo
        assert str(info) == '<CachedDataInfo>'

        assert await info.get_by_key('a') == 1
        it.mock_run.assert_called_once_with('a')

        it.mock_run.reset_mock()
        assert await info.get_by_key('b') == 2
        # value will be cached
        assert await info.get_by_key('b') == 2
        it.mock_run.assert_called_once_with('b')


@pytest.mark.asyncio
async def test_get_cached_info_basic_all():
    class CachedDataInfo(pobj.CachedInfoGroupEntry):
        @pobj.cached_info_property()
        async def keys(self):
            return await self.owner.run()

    class ClientForTest(ClientBaseForTest):
        info = CachedDataInfo.as_property()

    async with pmock.mock_client_run(ClientForTest) as it:
        it.mock_run.return_value = {'a': 1, 'b': 2}
        info = it.client.info

        assert (await info.keys)['a'] == 1
        assert (await info.keys)['b'] == 2
        it.mock_run.assert_called_once()

        del info.keys
        assert (await info.keys)['a'] == 1
        assert it.mock_run.call_count == 2


@pytest.mark.asyncio
async def test_get_cached_info_basic_iter():
    class CachedDataInfo(pobj.CachedInfoGroupEntry):
        @pobj.cached_info_property()
        async def keys(self):
            return await self.owner.run()

        @pobj.cached_info_property()
        async def a(self):
            return (await self.keys)['a']

        @pobj.cached_info_property()
        async def b(self):
            return (await self.keys)['b']

    class ClientForTest(ClientBaseForTest):
        info = CachedDataInfo.as_property()

    async with pmock.mock_client_run(ClientForTest) as it:
        it.mock_run.return_value = {'a': 1, 'b': 2}
        info = it.client.info

        assert await info.a == 1
        assert await info.b == 2
        it.mock_run.assert_called_once()

        async def func_a():
            assert await info.a == 1

        async def func_b():
            assert await info.b == 2

        del info.keys
        await asyncio.gather(func_a(), func_b())
        # because a and b are cached also.
        it.mock_run.assert_called_once()

        del info.a
        del info.b
        await asyncio.gather(func_a(), func_b())
        assert it.mock_run.call_count == 2


@pytest.mark.asyncio
async def test_get_cached_info_by_another_info():
    class CachedDataInfoFirst(pobj.CachedInfoGroupEntry):
        @pobj.cached_info_property()
        async def keys(self):
            return await self.owner.run()

    class CachedDataInfoSecond(pobj.CachedInfoGroupEntry):
        # first_info is a interface to access the values that are stores in CachedDataInfoFirst
        first_info = CachedDataInfoFirst.as_property()

        @pobj.cached_info_property()
        async def a(self):
            return (await self.first_info.keys)['a']

    class CachedDataInfoThird(pobj.CachedInfoGroupEntry):
        first_info = CachedDataInfoFirst.as_property()

        @pobj.cached_info_property()
        async def a(self):
            return (await self.first_info.keys)['a']

    class ClientForTest(ClientBaseForTest):
        info1 = CachedDataInfoFirst.as_property()
        info2 = CachedDataInfoSecond.as_property()
        info3 = CachedDataInfoThird.as_property()

    async with pmock.mock_client_run(ClientForTest) as it:
        it.mock_run.return_value = {'a': 1, 'b': 2}
        info1 = it.client.info1
        info2 = it.client.info2
        info3 = it.client.info3

        # value will be cached even by other property
        assert await info2.a == 1
        it.mock_run.assert_called_once_with()

        del info1.keys
        assert await info3.a == 1
        # cached value is not shared between different class
        assert it.mock_run.call_count == 2


@pytest.mark.asyncio
async def test_get_cached_info_by_obj_with_id():
    class CachedDataInfo(pobj.CachedInfoGroupEntry):
        @pobj.cached_info_property()
        async def keys(self):
            return await self.owner.run()

    class CachedDataInfoPerObj(pobj.CachedInfoGroupEntry):
        info = CachedDataInfo.as_property()

        @pobj.cached_info_property()
        async def value(self):
            return (await self.info.keys)[self.id]

    class ObjWithId(pobj.IdIdentifiedObj):
        info = CachedDataInfoPerObj.as_property()

    class ClientForTest(ClientBaseForTest):
        pass

    async with pmock.mock_client_run(ClientForTest) as it:
        it.mock_run.return_value = {'a': 1, 'b': 2}
        obj_a = ObjWithId(obj_id='a', owner=it.client)
        obj_b = ObjWithId(obj_id='b', owner=it.client)

        assert str(obj_a.info) == '<CachedDataInfoPerObj id=a>'
        assert str(obj_b.info) == '<CachedDataInfoPerObj id=b>'
        assert await obj_a.info.value == 1
        assert await obj_b.info.value == 2
