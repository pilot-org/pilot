import dataclasses
import contextlib
import mock
from loguru import logger
from typing import (
    Generic,
    TypeVar,
    Type,
)

from . import core as pcore
from . import connector as pconn
from . import spec as pspec

Client = TypeVar('Client', bound=pcore.Client)


class TestConnectAgent(pconn.ConnectAgent):
    required_enter_info_type = pconn.EnterInfo

    @classmethod
    def _connect(cls, *args, **kwargs):
        pass


@dataclasses.dataclass
class MockClientIT(Generic[Client]):
    client: Client
    mock_conn: mock.MagicMock
    mock_run: mock.MagicMock
    agent: Type[TestConnectAgent]


@contextlib.asynccontextmanager
async def mock_client_run(client_cls: Type[Client], *args, **kwargs):
    with mock.patch(f'{__name__}.TestConnectAgent._connect') as mock_connect:
        client_id = 'TEST'
        clients = {
            client_id:
            pspec.ClientSpec(force_client_type=client_cls,
                             connect_settings=[
                                 pspec.ConnectSetting(
                                     name='test',
                                     force_connect_agent=TestConnectAgent)
                             ])
        }
        mock_connection = mock.AsyncMock(spec=pconn.Connection)
        mock_connect.return_value.__aenter__ = mock.AsyncMock(
            return_value=mock_connection)
        async with pcore.ClientCachedPool(clients) as pool:
            client: Client = await pool.get_client(client_id, *args, **kwargs)
            mock_run = mock_connection.run
            it: MockClientIT[Client] = MockClientIT(client=client,
                                                    mock_conn=mock_connection,
                                                    mock_run=mock_run,
                                                    agent=TestConnectAgent)
            yield it


def mock_cmd_result(exit_status=0, stdout='', stderr=''):
    res = mock.MagicMock(spec=pconn.CmdRunResult)
    res.exit_status = exit_status
    res.stdout = stdout
    res.stderr = stderr
    return res
