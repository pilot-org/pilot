import pytest
import mock
import asyncclick as click

from pilot.client import connector as pconn
from pilot.client.connector.info import _local_info


def test_connect_info():
    with pytest.raises(TypeError):
        pconn.ConnectInfo()


@pytest.mark.parametrize('client_dict', [{
    'id': 't1',
    'host': 'localhost',
}, {
    'id': 't2',
    'username': 'admin',
}])
def test_remote_info(client_dict):
    with pytest.raises(TypeError):
        pconn.RemoteConnectInfo(*client_dict)


@pytest.mark.asyncio
@mock.patch('pilot.client.connector.core.ConnectBase._connect')
async def test_connect_base_yield(mock_connect):
    connection = mock.AsyncMock()
    mock_connect.return_value.__aenter__ = mock.AsyncMock(
        return_value=connection)
    client_info = mock.MagicMock(spec=pconn.ConnectInfo)
    async with pconn.ConnectBase.connect(client_info) as conn:
        assert conn == connection


@pytest.mark.asyncio
@mock.patch('pilot.client.connector.core.ConnectBase._connect')
async def test_connect_base_normal_args(mock_connect):
    client_info = mock.MagicMock(spec=pconn.ConnectInfo)
    async with pconn.ConnectBase.connect(client_info) as conn:
        mock_connect.assert_called_once_with(client_info)


@pytest.mark.asyncio
@mock.patch('pilot.client.connector.core.ConnectBase._connect')
@mock.patch('pilot.client.connector.core.ConnectBase.pass_connector', True)
async def test_connect_base_pass_connector_success(mock_connect):
    client_info = mock.MagicMock(spec=pconn.ConnectInfo)
    connector = mock.AsyncMock(spec=pconn.ConnectorCachedPool)
    async with pconn.ConnectBase.connect(client_info, connector=connector) as conn:
        mock_connect.assert_called_once_with(client_info, connector=connector)


@pytest.mark.asyncio
@mock.patch('pilot.client.connector.core.ConnectBase._connect')
@mock.patch('pilot.client.connector.core.ConnectBase.pass_connector', True)
async def test_connect_base_pass_connector_failed(mock_connect):
    client_info = mock.MagicMock(spec=pconn.ConnectInfo)
    with pytest.raises(click.UsageError):
        async with pconn.ConnectBase.connect(client_info) as conn:
            pass


@pytest.mark.asyncio
@mock.patch('pilot.client.connector.core.ConnectBase._connect')
@pytest.mark.urulogs('pilot.client.connector.core')
async def test_connect_base_show_connect_normal_log(mock_connect, urulogs):
    client_info = mock.MagicMock(spec=pconn.ConnectInfo)
    client_info.__repr__ = mock.MagicMock(return_value='TestClientInfo')
    async with pconn.ConnectBase.connect(client_info) as conn:
        assert urulogs.output == [
            'CONNECTION:pilot.client.connector.core:Start to exter TestClientInfo by ConnectBase',
            'CONNECTION:pilot.client.connector.core:Success to exter TestClientInfo by ConnectBase',
        ]
        urulogs.clear()
    assert urulogs.output == [
        'CONNECTION:pilot.client.connector.core:Success to exit TestClientInfo by ConnectBase',
        'CONNECTION:pilot.client.connector.core:Close TestClientInfo',
    ]


@pytest.mark.asyncio
@mock.patch('pilot.client.connector.core.ConnectBase._connect',
            side_effect=Exception)
@pytest.mark.urulogs('pilot.client.connector.core')
async def test_connect_base_show_connect_failed_log(mock_connect, urulogs):
    client_info = mock.MagicMock(spec=pconn.ConnectInfo)
    client_info.__repr__ = mock.MagicMock(return_value='TestClientInfo')
    with pytest.raises(Exception):
        async with pconn.ConnectBase.connect(client_info) as conn:
            # TODO: fix me
            assert urulogs.output == []


@pytest.mark.asyncio
@mock.patch('pilot.client.connector.core.ConnectBase._connect')
@pytest.mark.urulogs('pilot.client.connector.core')
async def test_connect_base_show_connect_failed_log_by_other(
        mock_connect, urulogs):
    client_info = mock.MagicMock(spec=pconn.ConnectInfo)
    client_info.__repr__ = mock.MagicMock(return_value='TestClientInfo')
    with pytest.raises(Exception):
        async with pconn.ConnectBase.connect(client_info) as conn:
            urulogs.clear()
            raise Exception('testcase')

    assert urulogs.output == [
        'WARNING:pilot.client.connector.core:Failed to do some operation on TestClientInfo by ConnectBase, due to testcase',
    ]


@pytest.mark.asyncio
@mock.patch('pilot.client.connector.core.ConnectLocalBase._connect')
async def test_connect_local_base_pass_client_info(mock_connect):
    async with pconn.ConnectLocalBase.connect() as conn:
        mock_connect.assert_called_once_with(_local_info)


@pytest.mark.asyncio
@mock.patch('pilot.client.connector.core.ConnectBase._connect')
async def testex_connector_connect_base(mock_connect):
    conn1 = mock.AsyncMock()
    conn2 = mock.AsyncMock()
    mock_connect.return_value.__aenter__ = mock.AsyncMock(
        side_effect=[conn1, conn2])
    connect_info = mock.MagicMock
    async with pconn.Connector() as connector:
        # Lasy connect
        mock_connect.assert_not_called()

        # equal use pcore.connect
        conn = await connector.connect(pconn.ConnectBase, connect_info)
        assert conn == conn1
        mock_connect.assert_called_once_with(connect_info)

        # connection will be cached
        assert await connector.connect(pconn.ConnectBase, connect_info) == conn

        # get other connection by conn_id
        conn = await connector.connect(pconn.ConnectBase, connect_info, sub_id='2')
        assert conn == conn2
        mock_connect.call_count == 2


@pytest.mark.asyncio
@mock.patch('pilot.client.connector.core.ConnectBase._connect')
async def test_connector_connect_local(mock_connect):
    conn1 = mock.AsyncMock()
    mock_connect.return_value.__aenter__ = mock.AsyncMock(
        return_value=conn1)
    async with pconn.Connector() as connector:
        conn = await connector.connect(pconn.ConnectLocalBase)
        assert conn == conn1
        mock_connect.assert_called_once_with(_local_info)

@pytest.mark.asyncio
@mock.patch('pilot.client.connector.core.ConnectBase._connect')
async def test_connector_close_all(mock_connect):
    conn1 = mock.AsyncMock()
    conn2 = mock.AsyncMock()
    conn3 = mock.AsyncMock()
    mock_connect.return_value.__aenter__ = mock.AsyncMock(
        side_effect=[conn1, conn2, conn3])
    async with pconn.Connector() as connector:
        await connector.connect(pconn.ConnectLocalBase)
        await connector.connect(pconn.ConnectLocalBase, sub_id='2')

        await connector.close_all()
        assert mock_connect.return_value.__aexit__.call_count == 2

        c3 = await connector.connect(pconn.ConnectLocalBase)
        assert c3 == conn3
        assert mock_connect.return_value.__aenter__.call_count == 3


@pytest.mark.asyncio
@mock.patch('pilot.client.connector.core.ConnectBase._connect')
async def test_connector_pool(mock_connect):
    client_info = mock.MagicMock(spec=pconn.ConnectInfo)
    async with pconn.ConnectorCachedPool() as pool:
        connector = await pool.get(client_info)
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
