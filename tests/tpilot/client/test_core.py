import pytest
import mock
import contextlib
import asyncio
import asyncclick as click
from omegaconf import OmegaConf
from loguru import logger

from pilot.client import connector as pconn
from pilot.client import core as pclient
from pilot.client import spec as pspec


@pytest.mark.asyncio
async def testex_subprocess_client_yaml():
    conf_content = '''
spec:
    client_type_path: pilot.client,SubprocessClient
    connect_settings:
        - connect_type_path: pilot.client.connector,Subprocess
host: 10.0.0.1
username: admin
    '''

    conf = OmegaConf.create(conf_content)
    client_info = pspec.ClientInfo.from_dict(conf)
    assert isinstance(client_info, pspec.ClientInfo)
    async with pclient.ClientCachedPool({'A': client_info}) as pool:
        client = await pool.get_client('A')
        assert isinstance(client, pclient.SubprocessClient)

        shell = await client.shell
        assert isinstance(shell, pconn.Subprocess.connection_cls)

        res = await shell.run('echo 1')
        assert isinstance(res, pconn.Subprocess.connection_cls.result_cls)
        assert res.stdout == '1\n'

        res = await client.run('echo 2')
        assert isinstance(res, pconn.Subprocess.connection_cls.result_cls)
        assert res.stdout == '2\n'


@pytest.mark.asyncio
async def testex_asyncssh_client_yaml(session_scoped_container_getter):
    remote = session_scoped_container_getter.get('ssh').network_info[0]
    conf_content = f'''
spec:
    client_type_path: pilot.client,AsyncsshClient
    connect_settings:
        - connect_type_path: pilot.client.connector,Asyncssh
          port: {remote.host_port}
host: {remote.hostname}
username: admin
password: test123
    '''
    conf = OmegaConf.create(conf_content)
    client_info = pspec.ClientInfo.from_dict(conf)
    assert isinstance(client_info, pspec.ClientInfo)
    async with pclient.ClientCachedPool({'A': client_info}) as pool:
        client = await pool.get_client('A')
        assert isinstance(client, pclient.AsyncsshClient)

        shell = await client.shell
        assert isinstance(shell, pconn.Asyncssh.connection_cls)

        res = await shell.run('echo 1')
        assert isinstance(res, pconn.Asyncssh.connection_cls.result_cls)
        assert res.stdout == '1\n'

        res = await client.run('echo 2')
        assert isinstance(res, pconn.Asyncssh.connection_cls.result_cls)
        assert res.stdout == '2\n'


'''
def gen_result(exit_status, stdout, stderr):
    return mock.MagicMock(**{
        'exit_status': exit_status,
        'stdout': stdout,
        'stderr': stderr
    })




def _mock_run(cmd):
    return _result_map[cmd]


class ForTestRunResult(pres.CmdRunResult):
    pass


class ForTestConn(pconn.Connection):
    result_cls = ForTestRunResult

    def __init__(self, *argv, run=None, tunnel=None, **kwargs):
        super().__init__(*argv, **kwargs)
        self.run_func = run
        self.argv = argv
        self.kwargs = kwargs
        self.tunnel = tunnel

    async def _run(self, *argv, **kwargs):
        if self.run_func is not None:
            if self.tunnel is not None:
                kwargs['tunnel'] = self.tunnel
            return self.run_func(*argv, **kwargs)


class TestClient(pclient.Client):
    pass


@pcore.wrap(register_name='for_test')
@contextlib.asynccontextmanager
async def connect(client_info, pre_conn=None, post_conn=None, **kwargs):
    if pre_conn is not None:
        pre_conn()
    yield ForTestConn(**kwargs)
    if post_conn is not None:
        post_conn()




@pytest.fixture
async def conn_for_test(request):
    marker = request.node.get_closest_marker('conn_for_test')
    if marker is None:
        raise RuntimeError(
            f'Please pass param by "@pytest.mark.conn_for_test(\'a.b.c\', level=\'DEBUG\')"'
        )

    test_client = pcore.ClientInfo({'id': 'test'})
    async with pcore.connect(test_client,
                             conn_type='for_test',
                             **marker.kwargs) as conn:
        yield conn


@pytest.fixture
async def client_getter(session_scoped_container_getter):
    remote = session_scoped_container_getter.get('ssh').network_info[0]
    clients = {
        'localhost': {
            'id': 'localhost',
        },
        'remote': {
            'id': 'remote',
            'host': remote.hostname,
            'port': int(remote.host_port),
            'username': 'admin',
            'password': 'test123',
        },
    }
    async with pclient.ClientGetter.start(clients) as runner:
        yield runner






@pytest.mark.asyncio
@pytest.mark.urulogs('pilot.client.connector.connection', level='CMD')
@pytest.mark.conn_for_test(run=_mock_run)
@pytest.mark.parametrize(
    'cmd,result',
    [('ls /123',
      gen_result(2, '',
                 'ls: cannot access \'/123\': No such file or directory'))])
async def test_connection_error(urulogs, conn_for_test, cmd, result):
    with pytest.raises(pres.ExitStatusNotSuccess):
        await conn_for_test.run(cmd)
    assert urulogs.output == [
        f'CMD:pilot.client.connector.connection:ForTestConn run: <(\'{cmd}\',)>'
    ]


@pytest.mark.asyncio
@pytest.mark.timeout(3, func_only=True)
@pytest.mark.parametrize('client,conn_type', [('localhost', 'subprocess'),
                                              ('remote', 'asyncssh')])
async def testi_multiple_exec_in_single_connect(client_getter, client,
                                                conn_type):
    conn = client_getter.get_client(client, TestClient, conn_type=conn_type)
    await asyncio.gather(conn.run('sleep 2'), conn.run('sleep 2'))


@pytest.mark.skip(reason='no way of currently login as root in openssh-server')
@pytest.mark.asyncio
@pytest.mark.parametrize('client,conn_type', [('remote', 'ssh_root_by_key')])
async def testi_connect_ssh_root_by_key(client_getter, client, conn_type):
    conn = client_getter.get_client(client, TestClient, conn_type=conn_type)
    res = await conn.run('id')
    assert res.stdout == 'uid=0(root) gid=0(root) groups=0(root)'
'''
