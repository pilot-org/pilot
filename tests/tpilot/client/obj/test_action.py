import pytest
import mock
from loguru import logger

from pilot.client import core as pclient
from pilot.client import mock as pmock
from pilot.client.obj import info as pinfo
from pilot.client.obj import state as pstate
from pilot.client.obj import action as pact


class ClientBaseForTest(pclient.Client):
    async def run(self, *args, **kwargs):
        conn = await self.connect('test')
        return await conn.run(*args, **kwargs)


mock_get_unique_state = mock.AsyncMock()


class SomethingStateEnum(pstate.StateEnum):
    DO_NOTHING = pstate.unique()
    CREATING = pstate.unique()
    FINISHED = pstate.unique()

    @classmethod
    def _get_target_obj_type(cls):
        return object

    @classmethod
    async def _get_unique_state(cls, check_target):
        await mock_get_unique_state(check_target)
        return await check_target.info.state


@pytest.mark.asyncio
async def testex_action_how_to_use():
    mock_state_getter = mock.AsyncMock()
    mock_clean = mock.MagicMock()
    mock_create = mock.AsyncMock()

    class CachedDataInfo(pinfo.CachedInfoGroupEntry):
        @pinfo.cached_info_property()
        async def state(self):
            return await mock_state_getter()

    class ClientForTest(ClientBaseForTest):
        info = CachedDataInfo.as_property()

        async def _try_to_create(self, *args, **kwargs):
            await mock_create(*args, **kwargs)

        def _clean_cache(self, target_obj) -> None:
            mock_clean(target_obj)
            del target_obj.info.state

        create_something = pact.Action.as_property(
            trigger_act_func=_try_to_create,
            clean_cache_func=_clean_cache,
            wanted_next_state=SomethingStateEnum.FINISHED,
            source_state={SomethingStateEnum.DO_NOTHING})

    # case 1
    mock_get_unique_state.reset_mock()
    mock_state_getter.side_effect = [
        SomethingStateEnum.DO_NOTHING,
        SomethingStateEnum.CREATING,
        SomethingStateEnum.FINISHED,
    ]
    async with pmock.mock_client_run(ClientForTest) as it:
        args = (1, 2)
        kwargs = {'a': 1, 'b': 2}
        creating = await it.client.create_something(*args, **kwargs)
        mock_create.assert_awaited_once_with(*args, **kwargs)
        mock_state_getter.assert_awaited_once()

        last_state = (await creating.wait_finish()).exit_state
        assert last_state == SomethingStateEnum.FINISHED
        assert mock_clean.call_count == 2

    # case 2: Failed to retry will be raise, because default max retry is 3 and finish is at 4.
    mock_clean.reset_mock()
    mock_get_unique_state.reset_mock()
    mock_state_getter.side_effect = [
        SomethingStateEnum.DO_NOTHING,
        SomethingStateEnum.CREATING,
        SomethingStateEnum.CREATING,
        SomethingStateEnum.FINISHED,
    ]
    async with pmock.mock_client_run(ClientForTest) as it:
        creating = await it.client.create_something()
        with pytest.raises(pact._UnexpectedStateError):
            await creating.wait_finish()
        assert mock_clean.call_count == 2

    # case 3: you can use max_get arg to change retry max
    mock_clean.reset_mock()
    mock_get_unique_state.reset_mock()
    mock_state_getter.side_effect = [
        SomethingStateEnum.DO_NOTHING,
        SomethingStateEnum.CREATING,
        SomethingStateEnum.CREATING,
        SomethingStateEnum.FINISHED,
    ]
    async with pmock.mock_client_run(ClientForTest) as it:
        creating = await it.client.create_something()
        last_state = (await creating.wait_finish(max_get=4)).exit_state
        assert last_state == SomethingStateEnum.FINISHED
        assert mock_clean.call_count == 3
