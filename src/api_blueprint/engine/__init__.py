
from api_blueprint.engine.group import RouterGroup
from api_blueprint.engine.router import Router
from api_blueprint.engine.provider import Provider
from typing import (
    List, Generator, Tuple, Final, Union, Type,
    Dict, Optional, DefaultDict, Callable,
)
from api_blueprint.engine.model import Model, Error, unwrap_errors, HeaderModel
from api_blueprint.engine.wrapper import ResponseWrapper, NoneWrapper
from fastapi import FastAPI
from enum import Enum


__GLOBAL_APP__: FastAPI = None


class Blueprint:
    root: str
    tags: List[str]
    pending_groups: List[RouterGroup]

    root_group: RouterGroup
    providers: List['Provider']
    errors: DefaultDict[int, List['Error']]
    response_wrapper: Type[ResponseWrapper] = ResponseWrapper
    headers: Optional[Union[HeaderModel, Type[HeaderModel]]] = None
    app: FastAPI

    is_built: bool = False
    upstream: Optional[str] = None

    def __init__(
        self, 
        root: str = '', 
        tags: List[str] = None, 
        providers: Optional[List['Provider']] = None,
        errors: Optional[List[Union[Model, Error]]] = None,
        response_wrapper: ResponseWrapper = NoneWrapper,
        headers: Optional[Union[HeaderModel, Type[HeaderModel]]] = None,
        app: FastAPI = None,
    ):
        global __GLOBAL_APP__

        self.root = root
        self.tags = tags or []
        self.root_group = RouterGroup(self, '')
        self.pending_groups = [self.root_group]
        self.providers = providers or []
        self.errors = unwrap_errors(errors or [])
        self.response_wrapper = response_wrapper
        self.headers = headers

        if app is None:
            if __GLOBAL_APP__ is None:
                __GLOBAL_APP__ = FastAPI(title=root.strip('/'))
            app = __GLOBAL_APP__

        self.app = app

        for method in ['POST', 'GET', 'PUT', 'DELETE', 'WS']:
            fn = getattr(self.root_group, method)
            setattr(self, method, fn)

    def __str__(self):
        return f'<Blueprint {self.root} groups[{len(self.pending_groups)}]>'

    def iter_router(self) -> Generator[Tuple[RouterGroup, Router], None, None]:
        for group in self.pending_groups:
            for router in group:
                yield (group, router)

    def group(self, prefix: str, **kwargs):
        group = RouterGroup(self, prefix, **kwargs)
        self.pending_groups.append(group)
        return group

    def POST(self, path: str = '', *, summary: str = None, desc: str = None) -> Router: ...
    def GET(self, path: str = '', *, summary: str = None, desc: str = None) -> Router: ...
    def PUT(self, path: str = '', *, summary: str = None, desc: str = None) -> Router: ...
    def DELETE(self, path: str = '', *, summary: str = None, desc: str = None) -> Router: ...
    def WS(self, path: str = '', *, summary: str = None, desc: str = None) -> Router: ...

    def build(self):
        if self.is_built:
            return
        self.is_built = True
        for group in self.pending_groups:
            group.build(self.app)

    def set_upstream(self, upstream: str):
        self.upstream = upstream

