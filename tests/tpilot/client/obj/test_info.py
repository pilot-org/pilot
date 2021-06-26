import pytest
import mock

from pilot.client import core as pclient
from pilot.client import obj as pobj


class CachedCalcUtil(pobj.CachedInfoGroupEntry):
    @pobj.cached_info(depend_on_id=False)
    async def add(self, a, b):
        return a + b

    @pobj.cached_info(depend_on_id=False)
    async def product(self, a, b):
        return a * b

    @pobj.cached_info(depend_on_id=False)
    async def get_by_key(self, key):
        return await self.client.run(key)


class AInfo(pobj.CachedInfoGroupEntry):
    _util = CachedCalcUtil.as_property()

    @pobj.cached_info_property
    async def a(self):
        return self._product(self._util.get_by_key('a'), 2)

    @pobj.cached_info_property
    async def a_product_2(self):
        return self._product(self.a, 2)

    @pobj.cached_info_property
    async def a_product_6(self):
        return self._product(self.product_2, 3)


class BInfo(pobj.CachedInfoGroupEntry):
    _util = CachedCalcUtil.as_property()

    @pobj.cached_info_property
    async def b(self):
        return self._product(self._util.get_by_key('b'), 2)

    @pobj.cached_info_property
    async def b_product_2(self):
        return self._product(self.b, 2)

    @pobj.cached_info_property
    async def b_product_6(self):
        return self._product(self.product_2, 3)


class MixInfo(pobj.CachedInfoGroupEntry):
    _util = CachedCalcUtil.as_property()
    a_info = AInfo.as_property()
    b_info = BInfo.as_property()

    @pobj.cached_info_property
    async def a3_add_b2(self):
        return self._util.add(self.a_info.a_product_3, self.b_info.b_product_2)


from loguru import logger


@pytest.mark.asyncio
async def test_get_internal_info():
    client = mock.AsyncMock(pclient.Client)
    client.run = mock.AsyncMock(return_value=1)
    client.obj_stores = {}
    client.info_getter_stores = {}
    client.run = mock.AsyncMock(return_value={'a': 1})
    with mock.patch.object(client, 'info', CachedCalcUtil.as_property()):
        logger.error(client)
        logger.error(client.info)