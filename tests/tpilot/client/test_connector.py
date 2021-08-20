import pytest
import mock
import asyncclick as click
from loguru import logger

from pilot.client import connector as pconn
from pilot.client.connector.info import _local_enter_info


class TestConnectAgent(pconn.ConnectAgent):
    required_enter_info_type = pconn.EnterInfo

    @classmethod
    def _connect(cls, *args, **kwargs):
        pass


class TestConnectLocalAgent(pconn.ConnectLocalAgent):
    required_enter_info_type = pconn.EnterInfo

    @classmethod
    def _connect(cls, *args, **kwargs):
        pass


@pytest.mark.asyncio
@mock.patch(f'{__name__}.TestConnectAgent._connect')
async def test_connect_agent_yield(mock_connect):
    connection = mock.AsyncMock()
    mock_connect.return_value.__aenter__ = mock.AsyncMock(
        return_value=connection)
    enter_info = mock.MagicMock(spec=pconn.EnterInfo)
    async with TestConnectAgent.connect(enter_info) as conn:
        assert conn == connection


@pytest.mark.asyncio
@mock.patch(f'{__name__}.TestConnectAgent._connect')
async def test_connect_agent_normal_args(mock_connect):
    client_info = mock.MagicMock(spec=pconn.EnterInfo)
    async with TestConnectAgent.connect(client_info) as conn:
        mock_connect.assert_called_once_with(client_info)


@pytest.mark.asyncio
@mock.patch(f'{__name__}.TestConnectAgent._connect')
@mock.patch(f'{__name__}.TestConnectAgent.pass_connector', True)
async def test_connect_agent_pass_connector_success(mock_connect):
    enter_info = mock.MagicMock(spec=pconn.EnterInfo)
    connector = mock.AsyncMock(spec=pconn.ConnectorCachedPool)
    async with TestConnectAgent.connect(enter_info,
                                        connector=connector) as conn:
        mock_connect.assert_called_once_with(enter_info, connector=connector)


@pytest.mark.asyncio
@mock.patch(f'{__name__}.TestConnectAgent._connect')
@mock.patch(f'{__name__}.TestConnectAgent.pass_connector', True)
async def test_connect_agent_pass_connector_failed(mock_connect):
    enter_info = mock.MagicMock(spec=pconn.EnterInfo)
    with pytest.raises(click.UsageError):
        async with TestConnectAgent.connect(enter_info) as conn:
            pass


@pytest.mark.asyncio
@mock.patch(f'{__name__}.TestConnectAgent._connect')
@pytest.mark.urulogs('pilot.client.connector.agent')
async def test_connect_agent_show_connect_normal_log(mock_connect, urulogs):
    enter_info = mock.MagicMock(spec=pconn.EnterInfo)
    enter_info.__repr__ = mock.MagicMock(return_value='TestEnterInfo')
    async with TestConnectAgent.connect(enter_info) as conn:
        assert urulogs.output == [
            'CONNECTION:pilot.client.connector.agent:Start to enter TestEnterInfo by TestConnectAgent',
            'CONNECTION:pilot.client.connector.agent:Success to enter TestEnterInfo by TestConnectAgent',
        ]
        urulogs.clear()
    assert urulogs.output == [
        'CONNECTION:pilot.client.connector.agent:Success to exit TestEnterInfo by TestConnectAgent',
        'CONNECTION:pilot.client.connector.agent:Close TestEnterInfo',
    ]


@pytest.mark.asyncio
@mock.patch(f'{__name__}.TestConnectAgent._connect', side_effect=Exception)
@pytest.mark.urulogs('pilot.client.connector.agent')
async def test_connect_agent_show_connect_failed_log(mock_connect, urulogs):
    enter_info = mock.MagicMock(spec=pconn.EnterInfo)
    enter_info.__repr__ = mock.MagicMock(return_value='TestEnterInfo')
    with pytest.raises(Exception):
        async with TestConnectAgent.connect(enter_info) as conn:
            # TODO: fix me
            assert urulogs.output == []


@pytest.mark.asyncio
@mock.patch(f'{__name__}.TestConnectAgent._connect')
@pytest.mark.urulogs('pilot.client.connector.agent')
async def test_connect_agent_show_connect_failed_log_by_other(
        mock_connect, urulogs):
    enter_info = mock.MagicMock(spec=pconn.EnterInfo)
    enter_info.__repr__ = mock.MagicMock(return_value='TestEnterInfo')
    with pytest.raises(Exception):
        async with TestConnectAgent.connect(enter_info) as conn:
            urulogs.clear()
            raise Exception('testcase')

    assert urulogs.output == [
        'WARNING:pilot.client.connector.agent:Failed to do some operation on TestEnterInfo by TestConnectAgent, due to testcase',
    ]


@pytest.mark.asyncio
@mock.patch(f'{__name__}.TestConnectLocalAgent._connect')
async def test_connect_local_agent_pass_client_info(mock_connect):
    async with TestConnectLocalAgent.connect() as conn:
        mock_connect.assert_called_once_with(_local_enter_info)


@pytest.mark.asyncio
@mock.patch(f'{__name__}.TestConnectAgent._connect')
async def testex_connector_connect_agent(mock_connect):
    conn1 = mock.AsyncMock()
    conn2 = mock.AsyncMock()
    mock_connect.return_value.__aenter__ = mock.AsyncMock(
        side_effect=[conn1, conn2])
    enter_info = mock.MagicMock(spec=pconn.EnterInfo)
    async with pconn.Connector() as connector:
        # Lasy connect
        mock_connect.assert_not_called()

        # equal use pcore.connect
        conn = await connector.connect_by_agent(TestConnectAgent,
                                                info=enter_info)
        assert conn == conn1
        mock_connect.assert_called_once_with(enter_info)

        # connection will be cached
        assert await connector.connect_by_agent(TestConnectAgent,
                                                info=enter_info) == conn

        # get other connection by conn_id
        conn = await connector.connect_by_agent(TestConnectAgent,
                                                info=enter_info,
                                                sub_id=2)
        assert conn == conn2
        mock_connect.call_count == 2


@pytest.mark.asyncio
@mock.patch(f'{__name__}.TestConnectLocalAgent._connect')
async def test_connector_connect_local(mock_connect):
    conn1 = mock.AsyncMock()
    mock_connect.return_value.__aenter__ = mock.AsyncMock(return_value=conn1)
    async with pconn.Connector() as connector:
        conn = await connector.connect_by_agent(TestConnectLocalAgent)
        assert conn == conn1
        mock_connect.assert_called_once_with(_local_enter_info)


@pytest.mark.asyncio
@mock.patch(f'{__name__}.TestConnectLocalAgent._connect')
async def test_connector_close_all(mock_connect):
    conn1 = mock.AsyncMock()
    conn2 = mock.AsyncMock()
    conn3 = mock.AsyncMock()
    mock_connect.return_value.__aenter__ = mock.AsyncMock(
        side_effect=[conn1, conn2, conn3])
    async with pconn.Connector() as connector:
        await connector.connect_by_agent(TestConnectLocalAgent)
        await connector.connect_by_agent(TestConnectLocalAgent, sub_id='2')

        await connector.close_all()
        assert mock_connect.return_value.__aexit__.call_count == 2

        c3 = await connector.connect_by_agent(TestConnectLocalAgent)
        assert c3 == conn3
        assert mock_connect.return_value.__aenter__.call_count == 3


@pytest.mark.asyncio
@mock.patch(f'{__name__}.TestConnectAgent._connect')
async def test_connector_pool(mock_connect):
    enter_info = mock.MagicMock(spec=pconn.EnterInfo)
    async with pconn.ConnectorCachedPool() as pool:
        connector = await pool.get(enter_info)
        assert isinstance(connector, pconn.Connector)


'''
_cmds = {
    'ls /home':
    mock.MagicMock(exit_status=0, stdout='Desktop Music Video', stderr=''),
    'ls /123':
    mock.MagicMock(
        exit_status=2,
        stdout='',
        stderr='ls: cannot access \'/123\': No such file or directory'),
}


def mock_run_cmd(cmd):
    return _cmds[cmd]


@pytest.mark.asyncio
@mock.patch('pilot.client.connector.connection.Connection._run')
@pytest.mark.urulogs('pilot.client.connector.connection')
@pytest.mark.parametrize('cmd', ['ls /home', 'ls /123'])
async def test_connection_result(mock_conn, urulogs, cmd):
    mock_conn.return_value = mock.AsyncMock(side_effect=mock_run_cmd)
    conn = pconn.Connection()
    res = await conn.run(cmd, check=False)
    assert res.origin.exit_status == res.exit_status
    assert res.origin.stdout == res.stdout
    assert res.origin.stderr == res.stderr
    assert urulogs.output == [
        f'CMD:pilot.client.connector.connection:ForTestConn run: <(\'{cmd}\',)>'
    ]
'''
