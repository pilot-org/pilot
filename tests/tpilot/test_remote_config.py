import unittest
import os

from sclick import cli
from pilot import remote_config


class TestRemoteConfig(unittest.IsolatedAsyncioTestCase):
    test_ds_name = 'B'
    test_path = '/tmp/.ssstool-test/test.json'

    async def test_write_and_read(self):
        test_json = {
            'test1': 1,
            'test2': '2',
        }
        repo = cli._CliRepo(cli._default_cfg_path)
        async with repo.manage_connection() as mgr_util:
            conn = await mgr_util.mgr.get_conn_by_name(self.test_ds_name)
            await conn.run(f'/bin/rm -rf {os.path.dirname(self.test_path)}')

            remoteCfg = remote_config.RemoteConfig(conn, self.test_path)
            await remoteCfg.write(test_json)
            self.assertDictEqual(await remoteCfg.read, test_json)
