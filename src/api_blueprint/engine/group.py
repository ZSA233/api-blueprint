from fastapi import APIRouter
from fastapi.types import IncEx
from enum import Enum
from typing import (
    List, Generic, TypeVar, Generator, Any, Dict, overload, Union,
    Optional, Type, TYPE_CHECKING
)
from api_blueprint.engine.provider import Provider
from api_blueprint.engine.wrapper import ResponseWrapper
from api_blueprint.engine.model import HeaderModel
from types import TracebackType
from pathlib import Path
from api_blueprint.engine.router import Router

if TYPE_CHECKING:
    from api_blueprint.engine import Blueprint


T = TypeVar('T')

class RouterGroup(Generic[T]):
    bp: 'Blueprint'
    branch: str
    pending_routers: List['Router']
    extra: Dict[str, Any]

    is_built: bool = False

    def __init__(self, bp: 'Blueprint', branch: str, **kwargs):
        self.bp = bp
        self.branch = branch
        self.pending_routers = []
        self.extra = kwargs or {}

    @property
    def prefix(self):
        return str(Path(self.bp.root) / (self.branch).lstrip('/'))

    @property
    def root(self):
        return self.bp.root

    def __str__(self):
        return f'<RouterGroup {self.prefix}>'

    def __iter__(self) -> Generator[Router, None, None]:
        for router in self.pending_routers:
            yield router

    def __len__(self) -> int:
        return len(self.pending_routers)

    def __enter__(self) -> 'RouterGroup':
        return self
    
    def __exit__(
            self, 
            exc_type: Optional[Type[BaseException]],
            exc_value: Optional[BaseException],
            traceback: Optional[TracebackType],
        ) -> Optional[bool]:
        self.build(self.bp.app)
        return None

    def build(self, app: str):
        if self.is_built:
            return
        self.is_built = True
        for router in self:
            router.do_register(app)

    @overload
    def POST(
        self,
        path: str = '',
        *,
        providers: Optional[List[Provider]] = None,
        headers: Optional[Union[HeaderModel, Type[HeaderModel]]] = None,
        response_wrapper: Optional[ResponseWrapper] = None,
        status_code: Optional[int] = None,
        tags: Optional[List[Union[str, Enum]]] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        response_description: str = "Successful Response",
        responses: Optional[Dict[Union[int, str], Dict[str, Any]]] = None,
        deprecated: Optional[bool] = None,
        operation_id: Optional[str] = None,
        response_model_include: Optional[IncEx] = None,
        response_model_exclude: Optional[IncEx] = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        openapi_extra: Optional[Dict[str, Any]] = None,
    ) -> Router: ...
    def POST(self, path: str = '', **kwargs: Dict[str, Any]):
        router =  Router(self, ['POST'], path, **kwargs)
        self.pending_routers.append(router)
        return router

    @overload
    def GET(
        self,
        path: str = '',
        *,
        providers: Optional[List[Provider]] = None,
        headers: Optional[Union[HeaderModel, Type[HeaderModel]]] = None,
        response_wrapper: Optional[ResponseWrapper] = None,
        status_code: Optional[int] = None,
        tags: Optional[List[Union[str, Enum]]] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        response_description: str = "Successful Response",
        responses: Optional[Dict[Union[int, str], Dict[str, Any]]] = None,
        deprecated: Optional[bool] = None,
        operation_id: Optional[str] = None,
        response_model_include: Optional[IncEx] = None,
        response_model_exclude: Optional[IncEx] = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        openapi_extra: Optional[Dict[str, Any]] = None,
    ) -> Router: ...
    def GET(self, path: str = '', **kwargs: Dict[str, Any]):
        router = Router(self, ['GET'], path, **kwargs)
        self.pending_routers.append(router)
        return router

    @overload
    def PUT(
        self,
        path: str = '',
        *,
        providers: Optional[List[Provider]] = None,
        headers: Optional[Union[HeaderModel, Type[HeaderModel]]] = None,
        response_wrapper: Optional[ResponseWrapper] = None,
        status_code: Optional[int] = None,
        tags: Optional[List[Union[str, Enum]]] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        response_description: str = "Successful Response",
        responses: Optional[Dict[Union[int, str], Dict[str, Any]]] = None,
        deprecated: Optional[bool] = None,
        operation_id: Optional[str] = None,
        response_model_include: Optional[IncEx] = None,
        response_model_exclude: Optional[IncEx] = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        openapi_extra: Optional[Dict[str, Any]] = None,
    ) -> Router: ...
    def PUT(self, path: str = '', **kwargs: Dict[str, Any]):
        router = Router(self, ['PUT'], path, **kwargs)
        self.pending_routers.append(router)
        return router
    
    @overload
    def DELETE(
        self,
        path: str = '',
        *,
        providers: Optional[List[Provider]] = None,
        headers: Optional[Union[HeaderModel, Type[HeaderModel]]] = None,
        response_wrapper: Optional[ResponseWrapper] = None,
        status_code: Optional[int] = None,
        tags: Optional[List[Union[str, Enum]]] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        response_description: str = "Successful Response",
        responses: Optional[Dict[Union[int, str], Dict[str, Any]]] = None,
        deprecated: Optional[bool] = None,
        operation_id: Optional[str] = None,
        response_model_include: Optional[IncEx] = None,
        response_model_exclude: Optional[IncEx] = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        openapi_extra: Optional[Dict[str, Any]] = None,
    ) -> Router: ...
    def DELETE(self, path: str = '', **kwargs: Dict[str, Any]):
        router = Router(self, ['DELETE'], path, **kwargs)
        self.pending_routers.append(router)
        return router


    @overload
    def WS(
        self,
        path: str = '',
        *,
        providers: Optional[List[Provider]] = None,
        headers: Optional[Union[HeaderModel, Type[HeaderModel]]] = None,
        response_wrapper: Optional[ResponseWrapper] = None,
        status_code: Optional[int] = None,
        tags: Optional[List[Union[str, Enum]]] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        response_description: str = "Successful Response",
        responses: Optional[Dict[Union[int, str], Dict[str, Any]]] = None,
        deprecated: Optional[bool] = None,
        operation_id: Optional[str] = None,
        response_model_include: Optional[IncEx] = None,
        response_model_exclude: Optional[IncEx] = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        openapi_extra: Optional[Dict[str, Any]] = None,
    ) -> Router: ...
    def WS(self, path: str = '', **kwargs: Dict[str, Any]):
        router = Router(self, ['WS'], path, **kwargs)
        self.pending_routers.append(router)
        return router