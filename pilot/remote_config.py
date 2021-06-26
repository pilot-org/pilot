import json
import os
import async_property

from pilot import utils


class RemoteConfig:
    def __init__(self, conn, cfg_path: str) -> None:
        self._conn = conn
        self._path: str = cfg_path

    @property
    async def read(self):
        return await self._readed_json

    @async_property.async_cached_property
    async def _readed_json(self):
        return await utils.get_json(self._conn, path=self._path)

    async def write(self, obj) -> None:
        await self._write_json(obj)

    async def _write_json(self, json_obj) -> None:
        await self._make_sure_dir_exists(os.path.dirname(self._path))

        json_str = json.dumps(json_obj)
        await self._conn.run(f'echo \'{json_str}\' > {self._path}')
        try:
            delattr(self._read_json)
        except AttributeError:
            pass

    async def _make_sure_dir_exists(self, dir_path: str) -> None:
        await self._conn.run(f'test -d {dir_path} || /bin/mkdir -p {dir_path}')