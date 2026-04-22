from __future__ import annotations

import time
from concurrent.futures.thread import ThreadPoolExecutor

import uvicorn
from fastapi import FastAPI

from api_blueprint import hub
from api_blueprint.config import Config
from api_blueprint.engine import Blueprint


def run_docs_server(conf: Config, entrypoints: list[Blueprint]) -> None:
    if (upstream := conf.golang.upstream) is not None:
        for entrypoint in entrypoints:
            entrypoint.set_upstream(upstream)

    docs_server = conf.blueprint.docs_server
    if not docs_server:
        raise Exception("[apidoc_server] 未指定docs服务 host:port")

    apps = list({bp.app for bp in entrypoints})
    host, hub_port = docs_server.split(":", 1)
    hub_port_int = int(hub_port)

    if len(apps) > 1:
        servers: list[uvicorn.Server] = []
        executor = ThreadPoolExecutor(len(apps))

        for app in apps:
            uvicorn_config = uvicorn.Config(app, host, port=0)
            uvicorn_server = uvicorn.Server(uvicorn_config)
            executor.submit(uvicorn_server.run)
            servers.append(uvicorn_server)

        app_port: dict[FastAPI, int] = {}
        for index, server in enumerate(servers):
            while True:
                if server.started:
                    sock = server.servers[0].sockets[0]
                    app_port[apps[index]] = sock.getsockname()[1]
                    break
                time.sleep(0.01)

        for app, port in app_port.items():
            hub.add_nav_items(app, f'http://{conf.blueprint.docs_domain or "localhost"}:{port}')

        uvicorn.run("api_blueprint.hub:app", host=host, port=hub_port_int)
        return

    uvicorn.run(apps[0], host=host, port=hub_port_int)
