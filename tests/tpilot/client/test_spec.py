import pytest
import mock
import dataclasses
import yaml
import asyncclick as click

from pilot.client import core as pclient
from pilot.client import connector as pconn
from pilot.client import spec as pspec


class TestConnectAgent(pconn.ConnectAgent):
    required_enter_info_type = pconn.EnterInfo

    @classmethod
    def _connect(cls, *args, **kwargs):
        pass


def testex_spec_must_supply_client():
    with pytest.raises(click.UsageError):
        pspec.ClientSpec()


def testex_spec_can_supply_client_type_directly():
    client_type = pclient.Client
    spec = pspec.ClientSpec(force_client_type=client_type)
    assert spec.client_type == client_type


def testex_spec_can_supply_client_type_str():
    spec = pspec.ClientSpec(client_type_path='pilot.client.core,Client')
    assert spec.client_type == pclient.Client


def testex_spec_connect_setting_type_check():
    with pytest.raises(click.UsageError):
        pspec.ConnectSetting(name='ssh', port=22)


def testex_spec_connect_setting_type_can_supply_connect_type_directly():
    conn_type = pconn.ConnectAgent
    setting = pspec.ConnectSetting(name='ssh',
                                   force_connect_agent=conn_type,
                                   port=22)
    assert setting.connect_agent == conn_type


def testex_spec_connect_setting_type_can_supply_connect_type_str():
    setting = pspec.ConnectSetting(
        name='ssh',
        connect_type_path='pilot.client.connector,ConnectAgent',
        port=22)
    assert setting.connect_agent == pconn.ConnectAgent


@pytest.mark.asyncio
@mock.patch(f'{__name__}.TestConnectAgent._connect')
async def testex_spec_get_connect_type_by_spec(mock_connect):
    enter_info = pconn.LoginSSHInfo(host='127.0.0.1',
                                    username='admin',
                                    password='123')
    ssh_conn_type = pspec.ConnectSetting(name='ssh',
                                         force_connect_agent=TestConnectAgent,
                                         args=(1, 2),
                                         kwargs={
                                             'a': 1,
                                             'b': 2,
                                         },
                                         port=22)
    http_conn_type = pspec.ConnectSetting(name='http',
                                          force_connect_agent=TestConnectAgent,
                                          args=[3, 4],
                                          kwargs={
                                              'c': 3,
                                              'd': 4,
                                          },
                                          port=80)
    spec = pspec.ClientSpec(force_client_type=pclient.Client,
                            connect_settings=[
                                ssh_conn_type,
                                http_conn_type,
                            ],
                            enter_info=enter_info)
    assert spec.connect_names == {'ssh', 'http'}
    enter_info2, args, kwargs = spec.get_enter_info('ssh')
    assert args == (1, 2)
    assert kwargs == {
        'a': 1,
        'b': 2,
    }
    assert dataclasses.replace(enter_info, port=22) == enter_info2

    enter_info3, args, kwargs = spec.get_enter_info('http')
    assert args == [3, 4]
    assert kwargs == {
        'c': 3,
        'd': 4,
    }
    assert dataclasses.replace(enter_info, port=80) == enter_info3

    conn = mock.AsyncMock()
    mock_connect.return_value.__aenter__ = mock.AsyncMock(return_value=conn)
    async with pconn.Connector() as connector:
        conn1 = await connector.connect_by_agent(TestConnectAgent,
                                                 'a',
                                                 info=enter_info,
                                                 id='b')
        assert conn == conn1
        mock_connect.assert_called_once_with(enter_info, 'a', id='b')

    mock_connect.reset_mock()
    async with spec.connect('ssh') as conn2:
        assert conn == conn2
        mock_connect.assert_called_once_with(dataclasses.replace(enter_info,
                                                                 port=22),
                                             1,
                                             2,
                                             a=1,
                                             b=2)


@pytest.mark.asyncio
async def testex_subprocess_client_yaml():
    conf_content = '''
client_type_path: pilot.client,SubprocessClient
connect_settings:
    - name: localhost
      connect_type_path: pilot.client.connector,SubprocessAgent
'''

    conf = yaml.load(conf_content)
    client_spec = pspec.ClientSpec.from_dict(conf)
    assert isinstance(client_spec, pspec.ClientSpec)
    async with pclient.ClientCachedPool({'A': client_spec}) as pool:
        client = await pool.get_client('A')
        assert isinstance(client, pclient.SubprocessClient)

        shell = await client.shell
        assert isinstance(shell, pconn.SubprocessAgent.connection_cls)

        res = await shell.run('echo 1')
        assert isinstance(res, pconn.SubprocessAgent.connection_cls.result_cls)
        assert res.stdout == '1\n'

        res = await client.run('echo 2')
        assert isinstance(res, pconn.SubprocessAgent.connection_cls.result_cls)
        assert res.stdout == '2\n'


@pytest.mark.asyncio
async def testex_asyncssh_client_yaml(session_scoped_container_getter):
    remote = session_scoped_container_getter.get('ssh').network_info[0]
    conf_content = f'''
A:
    client_type_path: pilot.client,AsyncsshClient
    connect_settings:
        - name: ssh
          connect_type_path: pilot.client.connector,AsyncsshAgent
          port: {remote.host_port}
    lazy_enter_info:
        host: {remote.hostname}
        username: admin
        password: test123
    '''
    conf = yaml.load(conf_content)
    async with pclient.ClientCachedPool.from_dict(conf) as pool:
        client = await pool.get_client('A')
        assert isinstance(client, pclient.AsyncsshClient)

        shell = await client.shell
        assert isinstance(shell, pconn.AsyncsshAgent.connection_cls)

        res = await shell.run('echo 1')
        assert isinstance(res, pconn.AsyncsshAgent.connection_cls.result_cls)
        assert res.stdout == '1\n'

        res = await client.run('echo 2')
        assert isinstance(res, pconn.AsyncsshAgent.connection_cls.result_cls)
        assert res.stdout == '2\n'