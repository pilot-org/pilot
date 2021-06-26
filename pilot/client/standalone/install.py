import asyncio
import dataclasses
import jinja2

from typing import Optional

from . import hook as phook

_install_list = []


@dataclasses.dataclass
class _InstallFile:
    source_path: str
    destination_path: str
    template_path: Optional[str] = None


_env = jinja2.Environment()


def register_install(file_path, dest_path, format_type=None):
    info = {'destination_path': dest_path}
    if format_type == 'jinja2' or file_path.endswith('.jinja2'):
        info['template_path'] = file_path
        with open(file_path, 'r') as f:
            template = _env.from_string(f.read())
            result = template.render(**scli.config)

            new_path = file_path[:-len('.jinja2')]
            with open(new_path, 'w') as f:
                f.write(result)
            info['source_path'] = new_path
    else:
        info['source_path'] = file_path

    _install_list.append(_InstallFile(**info))


async def install_on_client(client):
    # 1. scp all git files
    # 2. run install.sh all
    await asyncio.gather(*[
        client.run(f'/bin/mkdir -p {dir_path}')
        for dir_path in phook.enum_hook()
    ])
