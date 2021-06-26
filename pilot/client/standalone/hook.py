import os
import asyncio

_hook_map = {}


def enum_hook():
    return list(_hook_map.keys())


def register_hook(key, value):
    _hook_map[key] = value


async def trigger_hook(client, hook):
    dir_path = _hook_map[hook]

    need_trigger_hooks = []
    for name in os.listdir(dir_path):
        path = os.path.join(dir_path, name)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            need_trigger_hooks.append(path)

    await asyncio.gather(
        *[client.run(exec_path) for exec_path in need_trigger_hooks])
