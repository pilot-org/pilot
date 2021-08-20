import pytest

from pilot.client import core as pclient
from pilot.client import info as pinfo
from pilot.client import mock as pmock


class ClientBaseForTest(pclient.Client):
    async def run(self, *args, **kwargs):
        conn = await self.connect('test')
        return await conn.run(*args, **kwargs)


@pytest.mark.asyncio
async def test_ip_addr():
    class ClientForTest(ClientBaseForTest):
        info = pinfo.NetworkInfo.as_property()

    async with pmock.mock_client_run(ClientForTest) as it:
        it.mock_run.return_value = pmock.mock_cmd_result(
            exit_status=0,
            stdout=
            '''1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host
       valid_lft forever preferred_lft forever
2: sit0: <NOARP> mtu 1480 qdisc noop state DOWN
    link/sit 0.0.0.0 brd 0.0.0.0
3: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP qlen 1000
    link/ether 00:11:32:aa:bb:20 brd ff:ff:ff:ff:ff:ff
    inet 10.17.32.103/21 brd 10.17.39.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet6 fe80::211:32ff:feaa:bb20/64 scope link
       valid_lft forever preferred_lft forever
4: eth1: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc mq state DOWN qlen 1000
    link/ether 00:11:32:aa:bb:21 brd ff:ff:ff:ff:ff:ff
    inet 169.254.102.29/16 brd 169.254.255.255 scope global eth1
       valid_lft forever preferred_lft forever
5: eth2: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc mq state DOWN qlen 1000
    link/ether 00:11:32:aa:bb:22 brd ff:ff:ff:ff:ff:ff
    inet 169.254.106.166/16 brd 169.254.255.255 scope global eth2
       valid_lft forever preferred_lft forever
6: eth3: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc mq state DOWN qlen 1000
    link/ether 00:11:32:aa:bb:23 brd ff:ff:ff:ff:ff:ff
    inet 169.254.104.94/16 brd 169.254.255.255 scope global eth3
       valid_lft forever preferred_lft forever
''',
            stderr='')
        info = it.client.info
        ip_info_enum = await info.ip_info_enum
        assert ip_info_enum == {
            'lo':
            pinfo._IpInfo('lo', '127.0.0.1', '00:00:00:00:00:00', 8),
            'eth0':
            pinfo._IpInfo('eth0', '10.17.32.103', '00:11:32:aa:bb:20', 21),
            'eth1':
            pinfo._IpInfo('eth1', '169.254.102.29', '00:11:32:aa:bb:21', 16),
            'eth2':
            pinfo._IpInfo('eth2', '169.254.106.166', '00:11:32:aa:bb:22', 16),
            'eth3':
            pinfo._IpInfo('eth3', '169.254.104.94', '00:11:32:aa:bb:23', 16)
        }
        it.mock_run.assert_awaited_once_with('/sbin/ip addr',
                                             redirect_stderr_tty=True,
                                             read_only=True)

        # check ip_info_enum is cached
        assert ip_info_enum == await info.ip_info_enum
