from __future__ import annotations

from typing import DefaultDict, Generator, Optional, Union

from fastapi import FastAPI

from api_blueprint.engine.blueprint.group import RouterGroup
from api_blueprint.engine.blueprint.identity import blueprint_root_slug, normalize_blueprint_name
from api_blueprint.engine.blueprint.router import Router
from api_blueprint.engine.runtime import CodeMessageDataEnvelope, Provider, ResponseEnvelope, get_shared_app
from api_blueprint.engine.schema import Error, HeaderModel, Model, unwrap_errors


class Blueprint:
    root: str
    name: str
    root_slug: str
    tags: list[str]
    pending_groups: list[RouterGroup]

    root_group: RouterGroup
    providers: list["Provider"]
    errors: DefaultDict[int, list["Error"]]
    response_envelope: type[ResponseEnvelope] = ResponseEnvelope
    headers: Optional[Union[HeaderModel, type[HeaderModel]]] = None
    app: FastAPI

    is_built: bool = False
    upstream: Optional[str] = None

    def __init__(
        self,
        root: str = "",
        tags: list[str] | None = None,
        providers: Optional[list["Provider"]] = None,
        errors: Optional[list[Union[Model, Error]]] = None,
        response_envelope: type[ResponseEnvelope] = CodeMessageDataEnvelope,
        headers: Optional[Union[HeaderModel, type[HeaderModel]]] = None,
        app: FastAPI | None = None,
        name: str | None = None,
    ):
        self.root = root
        self.name = normalize_blueprint_name(name=name, root=root)
        self.root_slug = blueprint_root_slug(self.name)
        self.tags = tags or []
        self.root_group = RouterGroup(self, "")
        self.pending_groups = [self.root_group]
        self.providers = providers or []
        self.errors = unwrap_errors(errors or [])
        self.response_envelope = response_envelope
        self.headers = headers
        self.app = app or get_shared_app(self.name)

        for method in ["POST", "GET", "PUT", "DELETE", "STREAM", "CHANNEL"]:
            setattr(self, method, getattr(self.root_group, method))

    def __str__(self) -> str:
        return f"<Blueprint {self.name} root={self.root} groups[{len(self.pending_groups)}]>"

    def iter_router(self) -> Generator[tuple[RouterGroup, Router], None, None]:
        for group in self.pending_groups:
            for router in group:
                yield group, router

    def group(self, prefix: str, **kwargs):
        group = RouterGroup(self, prefix, **kwargs)
        self.pending_groups.append(group)
        return group

    def POST(self, path: str = "", *, summary: str = None, desc: str = None) -> Router: ...
    def GET(self, path: str = "", *, summary: str = None, desc: str = None) -> Router: ...
    def PUT(self, path: str = "", *, summary: str = None, desc: str = None) -> Router: ...
    def DELETE(self, path: str = "", *, summary: str = None, desc: str = None) -> Router: ...
    def STREAM(self, path: str = "", *, summary: str = None, desc: str = None) -> Router: ...
    def CHANNEL(self, path: str = "", *, summary: str = None, desc: str = None) -> Router: ...

    def build(self) -> None:
        if self.is_built:
            return
        self.is_built = True
        for group in self.pending_groups:
            group.build(self.app)

    def set_upstream(self, upstream: str) -> None:
        self.upstream = upstream
