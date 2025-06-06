from api_blueprint.engine import Blueprint
from api_blueprint.config import Config
from api_blueprint.helper import load_entrypoints
from api_blueprint import hub
from concurrent.futures.thread import ThreadPoolExecutor
from pathlib import Path
from fastapi import FastAPI
import typing
import uvicorn
import click
import time


def run_apidoc_server(conf: Config, entrypoints: typing.List[Blueprint]):
    if (upstream := conf.golang.upstream) is not None:
        for ep in entrypoints:
            ep.set_upstream(upstream)

    docs_server = conf.blueprint.docs_server
    if not docs_server:
        raise Exception(f'[apidoc_server] 未指定docs服务 host:port')

    apps = list({bp.app for bp in entrypoints})
    
    host, hub_port = docs_server.split(':', 1)
    hub_port = int(hub_port)
    if len(apps) > 1:
        servers: typing.List[uvicorn.Server] = []
        executor = ThreadPoolExecutor(len(apps))

        for app in apps:
            uvicorn_conf = uvicorn.Config(app, host, port=0)
            uvicorn_server = uvicorn.Server(uvicorn_conf)
            executor.submit(uvicorn_server.run)
            servers.append(uvicorn_server)

        app_port: typing.Dict[FastAPI, int] = {}
        for i, svr in enumerate(servers):
            while True:
                if svr.started:
                    sock = svr.servers[0].sockets[0]
                    app_port[apps[i]] = sock.getsockname()[1]
                    break   
                time.sleep(0.01)

        for app, port in app_port.items():
            hub.add_nav_items(app, f'http://{conf.blueprint.docs_domain or "localhost"}:{port}')

        uvicorn.run(
            "api_blueprint.hub:app",
            host=host,
            port=hub_port
        )
    else:
        uvicorn.run(
            apps[0],
            host=host,
            port=hub_port
        )


@click.command()
@click.option('-c', '--config', default='./api-blueprint.toml', help='配置文件')
def apidoc_server(config: typing.Optional[str] = './api-blueprint.toml'):
    c = Path(config).absolute()
    if c.is_dir():
        c /= 'api-blueprint.toml'
    if not c.exists():
        raise FileNotFoundError(f'[apidoc_server] --config 配置文件[{c}]不存在')
    conf = Config.load(c)

    relative_path: Path = c.parent
    entrypoints = load_entrypoints(conf.blueprint.entrypoints, relative_path)
    if not entrypoints:
        raise ModuleNotFoundError(f'[apidoc_server] 未指定蓝图entrypoints')
    
    for ep in entrypoints:
        ep.build()

    run_apidoc_server(conf, entrypoints)