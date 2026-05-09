from __future__ import annotations

import time
from concurrent.futures.thread import ThreadPoolExecutor

import click
import uvicorn
from fastapi import FastAPI

from api_blueprint import hub
from api_blueprint.config import Config
from api_blueprint.engine import Blueprint


def _docs_upstream(conf: Config) -> str | None:
    # `api-doc-server` no longer has a vnext config source for an upstream URL.
    # Keep a defensive legacy fallback so the command does not crash if an
    # out-of-tree caller still passes an object exposing `golang.upstream`.
    legacy_golang = getattr(conf, "golang", None)
    if legacy_golang is None:
        return None
    return getattr(legacy_golang, "upstream", None)


def _docs_display_host(conf: Config, host: str) -> str:
    docs_domain = conf.blueprint.docs_domain if conf.blueprint is not None else None
    if docs_domain:
        return docs_domain
    if host in {"0.0.0.0", "::", "[::]"}:
        return "localhost"
    return host


def _app_docs_path(app: FastAPI) -> str:
    return app.docs_url or "/docs"


def _join_http_url(host: str, port: int | str, path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"http://{host}:{port}{normalized_path}"


def _serve_uvicorn(app: FastAPI | str, host: str, port: int, url: str, label: str) -> None:
    uvicorn_config = uvicorn.Config(app, host=host, port=port)
    socket = uvicorn_config.bind_socket()
    actual_port = socket.getsockname()[1]
    click.echo(f"[api-doc-server] {label}: {url.format(port=actual_port)}")
    uvicorn_server = uvicorn.Server(uvicorn_config)
    uvicorn_server.run(sockets=[socket])


def run_docs_server(conf: Config, entrypoints: list[Blueprint]) -> None:
    upstream = _docs_upstream(conf)
    if upstream is not None:
        for entrypoint in entrypoints:
            entrypoint.set_upstream(upstream)

    if conf.blueprint is None:
        raise ValueError("[apidoc_server] 配置中未找到blueprint段落")

    docs_server = conf.blueprint.docs_server
    if not docs_server:
        raise Exception("[apidoc_server] 未指定docs服务 host:port")

    apps = list({bp.app for bp in entrypoints})
    host, hub_port = docs_server.split(":", 1)
    hub_port_int = int(hub_port)
    display_host = _docs_display_host(conf, host)

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
            hub.add_nav_items(app, _join_http_url(display_host, port, _app_docs_path(app)))

        _serve_uvicorn(
            "api_blueprint.hub:app",
            host,
            hub_port_int,
            _join_http_url(display_host, "{port}", "/"),
            "Hub",
        )
        return

    _serve_uvicorn(
        apps[0],
        host,
        hub_port_int,
        _join_http_url(display_host, "{port}", _app_docs_path(apps[0])),
        "Docs",
    )
