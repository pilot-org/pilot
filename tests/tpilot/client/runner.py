import unittest
import pytest
import contextlib
import asyncio
import mock

from pilot.client.connector import connection as pconn
from pilot.client.connector import result as pres
from pilot.client.connector import subprocess as pconn

from loguru import logger

pytest_plugins = ["docker_compose"]

#logger.remove()


class UruTest(unittest.IsolatedAsyncioTestCase):
    @contextlib.contextmanager
    def assertLogs(self, *argv, **kwargs):
        handler = unittest.case._CapturingHandler()
        tmp = logger.add(
            handler,
            format='{level}:{name}:{message}',
            #filter=self._prefix,
            level=kwargs.get('level'))
        yield handler.watcher
        logger.complete()
        logger.remove(tmp)


# TODO: use pytest then remove this


class A(pit.ClientInterface):
    export_as_client = True


class B(pit.ClientInterface):
    pass


class C(pit.ClientInterface):
    export_as_client = True
    checked_attrs = pit.ClientInterface.checked_attrs + ['os']


class D(pit.RemoteClientInterface):
    export_as_client = True


class TestClientInfo(unittest.TestCase):
    def test_get_client_info(self):
        client_info = pit.ClientInfo({'id': 'A', 'client_type': 'A'})
        self.assertIsInstance(client_info, pit.ClientInfo)

    def test_check_attr(self):
        cases = [{'id': 'C', 'os': 'ubuntu'}]
        for info_map in cases:
            with self.subTest(info_map=info_map):
                with self.assertRaises(ValueError):
                    pit.ClientInfo(info_map)

    def test_check_remote_client_info(self):
        info = {'id': 'D', 'client_type': 'D'}
        cases = [info.copy(), info.copy()]
        cases[0].update({'host': 'localhost'}),
        cases[1].update({'usrname': 'admin'})
        for info_map in cases:
            with self.subTest(info_map=info_map):
                with self.assertRaises(ValueError):
                    pit.ClientInfo(info_map)


class ForTestRunResult(pres.RunResult):
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


class ForTestInterface(pit.ClientInterface):
    export_as_client = True

    def __init__(self, *argv, conn=None, run=None, **kwargs):
        super().__init__(*argv, **kwargs)
        self._conn = conn
        self._run = run

    def __repr__(self):
        return self.__class__.__name__

    @contextlib.asynccontextmanager
    async def _connect(self, **kwargs):
        if self._conn is not None:
            self._conn()
        yield ForTestConn(run=self._run, **kwargs)


def get_client(**kwargs):
    client_info = pit.ClientInfo({
        'id': 'test',
        'client_type': 'ForTestInterface',
    })
    return ForTestInterface(client_info, **kwargs)


class TestClientConnect(UruTest):
    async def test_pass_parent_client(self):
        client = get_client()
        with self.assertLogs('pilot.client.interface', level='INFO') as cm:
            async with client.connect() as conn:
                self.assertEqual(conn.kwargs.get('parent_client'), client)

    async def test_log(self):
        client = get_client()
        with self.assertLogs('pilot.client.runner.interface',
                             level='INFO') as cm:
            async with client.connect() as conn:
                pass
        self.assertEqual(cm.output, [
            'INFO:pilot.client.runner.interface:Start to enter ForTestInterface',
            'INFO:pilot.client.runner.interface:Success to enter ForTestInterface',
            'INFO:pilot.client.runner.interface:Success to exit ForTestInterface',
            'INFO:pilot.client.runner.interface:Close ForTestInterface'
        ])

    async def test_connect_error_and_test_log(self):
        error_msg = 'test'

        def error():
            raise RuntimeError(error_msg)

        client = get_client(conn=error)
        with self.assertLogs('pilot.client.runner.interface',
                             level='INFO') as cm:
            with self.assertRaises(RuntimeError):
                async with client.connect() as conn:
                    pass
        self.assertEqual(cm.output, [
            'INFO:pilot.client.runner.interface:Start to enter ForTestInterface',
            f'WARNING:pilot.client.runner.interface:Failed to enter ForTestInterface, due to {error_msg}',
        ])


class ForTestWithTunnelClient(ForTestInterface):
    export_as_client = True

    @contextlib.asynccontextmanager
    async def _connect(self, **kwargs):
        tunnel = await self.get_tunnel()
        yield ForTestConn(run=self._run, tunnel=tunnel, **kwargs)


def get_client_by_tunnel(tunnel, **kwargs):
    client_info = pit.ClientInfo({
        'id': 'test',
        'tunnel': tunnel,
    })
    return pget.CachedClientGetter.gen_interface(client_info,
                                                 'ForTestWithTunnelClient',
                                                 **kwargs)


class TestClientTunnel(UruTest):
    async def test_tunnel_is_none(self):
        client = get_client_by_tunnel(tunnel=None)
        with self.assertLogs('pilot.client.runner.interface',
                             level='INFO') as cm:
            async with client.connect() as conn:
                pass

    async def test_tunnel_is_obj(self):
        tunnel = get_client()

        def run_by_tunnel(pass_tunnel):
            self.assertEqual(pass_tunnel, tunnel)

        client = get_client_by_tunnel(tunnel=tunnel, run=run_by_tunnel)
        with self.assertLogs('pilot.client.runner.interface',
                             level='INFO') as cm:
            async with client.connect() as conn:
                pass

    def test_tunne_is_client_info(self):
        # TODO
        pass

    def test_tunne_is_id(self):
        # TODO
        pass


def gen_result(exit_status, stdout, stderr):
    return mock.MagicMock(**{
        'exit_status': exit_status,
        'stdout': stdout,
        'stderr': stderr
    })


result_map = {
    'ls /home':
    gen_result(0, 'Desktop Music Video', ''),
    'ls /123':
    gen_result(2, '', 'ls: cannot access \'/123\': No such file or directory')
}


def run(cmd):
    return result_map[cmd]


class TestConnection(UruTest):
    async def test_nomal(self):
        cmd = 'ls /home'
        client = get_client(run=run)
        with self.assertLogs('pilot.client.runner.interface.connect',
                             level='INFO') as _:
            async with client.connect() as conn:
                with self.assertLogs('pilot.client.runner.connection',
                                     level='INFO') as cm:
                    result = await conn.run(cmd)
                    self.assertIsInstance(result, ForTestRunResult)
                self.assertEqual(cm.output, [
                    f'INFO:pilot.client.runner.connection:ForTestConn run: <{cmd}>'
                ])

    async def test_error(self):
        cmd = 'ls /123'
        client = get_client(run=run)
        with self.assertLogs('pilot.client.runner.interface.connect',
                             level='INFO') as _:
            async with client.connect() as conn:
                with self.assertLogs('pilot.client.runner.connection',
                                     level='INFO') as cm:
                    with self.assertRaises(pres.ExitStatusNotSuccess) as c:
                        result = await conn.run(cmd)
                self.assertEqual(cm.output, [
                    f'INFO:pilot.client.runner.connection:ForTestConn run: <{cmd}>'
                ])

    async def test_redirect(self):
        # TODO: test redirect_tty, redirect_stdout_tty, redirect_stderr_tty
        pass


@pytest.fixture
async def client_getter(session_scoped_container_getter):
    remote = session_scoped_container_getter.get('ssh').network_info[0]
    clients = {
        'localhost': {
            'id': 'localhost',
            'client_type': 'SubprocessClient'
        },
        'remote': {
            'id': 'remote',
            'client_type': 'AsyncSshClient',
            'host': remote.hostname,
            'port': remote.host_port,
            'username': 'admin',
            'password': 'test123',
        },
        'remote_by_expect': {
            'id': 'remote_by_expect',
            'client_type': 'AsyncSshAnotherUserClient',
            'host': remote.hostname,
            'port': remote.host_port,
            'username': 'root',
            'bridge': {
                'host': remote.hostname,
                'port': remote.host_port,
                'username': 'admin',
                'password': 'test123',
            }
        }
    }
    async with pget.CachedClientGetter(clients) as getter:
        yield getter


@pytest.mark.asyncio
@pytest.mark.timeout(3, func_only=True)
@pytest.mark.parametrize('client,it_type', [('localhost', 'SubprocessClient'),
                                            ('remote', 'AsyncSshClient')])
async def testi_multiple_exec_in_single_connect(client_getter, client,
                                                it_type):
    conn = await client_getter.get_connection_by_id(client, it_type)
    await asyncio.gather(conn.run('sleep 2'), conn.run('sleep 2'))
