from __future__ import annotations

from enum import Enum
from types import TracebackType
from typing import TYPE_CHECKING, Any, Generic, Optional, TypeVar, Union, overload

from fastapi.types import IncEx

from api_blueprint.engine.blueprint.router import Router
from api_blueprint.engine.runtime import Handle, Provider, ResponseWrapper, WsHandle
from api_blueprint.engine.schema import HeaderModel
from api_blueprint.engine.utils import join_url_path

if TYPE_CHECKING:
    from api_blueprint.engine.blueprint.core import Blueprint


T = TypeVar("T")


class RouterGroup(Generic[T]):
    bp: "Blueprint"
    branch: str
    pending_routers: list[Router]
    extra: dict[str, Any]

    is_built: bool = False

    def __init__(self, bp: "Blueprint", branch: str, **kwargs: Any):
        self.bp = bp
        self.branch = branch
        self.pending_routers = []
        self.extra = kwargs or {}

    @property
    def prefix(self):
        return join_url_path(self.bp.root, self.branch)

    @property
    def root(self):
        return self.bp.root

    def __str__(self) -> str:
        return f"<RouterGroup {self.prefix}>"

    def __iter__(self):
        yield from self.pending_routers

    def __len__(self) -> int:
        return len(self.pending_routers)

    def __enter__(self) -> "RouterGroup":
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        self.build(self.bp.app)
        return None

    def build(self, app: str) -> None:
        if self.is_built:
            return
        self.is_built = True
        for router in self:
            router.do_register(app)

    @overload
    def POST(
        self,
        path: str = "",
        *,
        handle_data: str = None,
        providers: Optional[list[Provider]] = None,
        headers: Optional[Union[HeaderModel, type[HeaderModel]]] = None,
        response_wrapper: Optional[ResponseWrapper] = None,
        status_code: Optional[int] = None,
        tags: Optional[list[Union[str, Enum]]] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        response_description: str = "Successful Response",
        responses: Optional[dict[Union[int, str], dict[str, Any]]] = None,
        deprecated: Optional[bool] = None,
        operation_id: Optional[str] = None,
        response_model_include: Optional[IncEx] = None,
        response_model_exclude: Optional[IncEx] = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        openapi_extra: Optional[dict[str, Any]] = None,
    ) -> Router: ...

    def POST(self, path: str = "", *, handle_data: str = None, **kwargs: dict[str, Any]):
        router = Router(self, ["POST"], path, handle=Handle(handle_data), **kwargs)
        self.pending_routers.append(router)
        return router

    @overload
    def GET(
        self,
        path: str = "",
        *,
        handle_data: str = None,
        providers: Optional[list[Provider]] = None,
        headers: Optional[Union[HeaderModel, type[HeaderModel]]] = None,
        response_wrapper: Optional[ResponseWrapper] = None,
        status_code: Optional[int] = None,
        tags: Optional[list[Union[str, Enum]]] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        response_description: str = "Successful Response",
        responses: Optional[dict[Union[int, str], dict[str, Any]]] = None,
        deprecated: Optional[bool] = None,
        operation_id: Optional[str] = None,
        response_model_include: Optional[IncEx] = None,
        response_model_exclude: Optional[IncEx] = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        openapi_extra: Optional[dict[str, Any]] = None,
    ) -> Router: ...

    def GET(self, path: str = "", *, handle_data: str = None, **kwargs: dict[str, Any]):
        router = Router(self, ["GET"], path, handle=Handle(handle_data), **kwargs)
        self.pending_routers.append(router)
        return router

    @overload
    def PUT(
        self,
        path: str = "",
        *,
        handle_data: str = None,
        providers: Optional[list[Provider]] = None,
        headers: Optional[Union[HeaderModel, type[HeaderModel]]] = None,
        response_wrapper: Optional[ResponseWrapper] = None,
        status_code: Optional[int] = None,
        tags: Optional[list[Union[str, Enum]]] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        response_description: str = "Successful Response",
        responses: Optional[dict[Union[int, str], dict[str, Any]]] = None,
        deprecated: Optional[bool] = None,
        operation_id: Optional[str] = None,
        response_model_include: Optional[IncEx] = None,
        response_model_exclude: Optional[IncEx] = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        openapi_extra: Optional[dict[str, Any]] = None,
    ) -> Router: ...

    def PUT(self, path: str = "", *, handle_data: str = None, **kwargs: dict[str, Any]):
        router = Router(self, ["PUT"], path, handle=Handle(handle_data), **kwargs)
        self.pending_routers.append(router)
        return router

    @overload
    def DELETE(
        self,
        path: str = "",
        *,
        handle_data: str = None,
        providers: Optional[list[Provider]] = None,
        headers: Optional[Union[HeaderModel, type[HeaderModel]]] = None,
        response_wrapper: Optional[ResponseWrapper] = None,
        status_code: Optional[int] = None,
        tags: Optional[list[Union[str, Enum]]] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        response_description: str = "Successful Response",
        responses: Optional[dict[Union[int, str], dict[str, Any]]] = None,
        deprecated: Optional[bool] = None,
        operation_id: Optional[str] = None,
        response_model_include: Optional[IncEx] = None,
        response_model_exclude: Optional[IncEx] = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        openapi_extra: Optional[dict[str, Any]] = None,
    ) -> Router: ...

    def DELETE(self, path: str = "", *, handle_data: str = None, **kwargs: dict[str, Any]):
        router = Router(self, ["DELETE"], path, handle=Handle(handle_data), **kwargs)
        self.pending_routers.append(router)
        return router

    @overload
    def WS(
        self,
        path: str = "",
        *,
        handle_data: list[str] = [],
        providers: Optional[list[Provider]] = None,
        headers: Optional[Union[HeaderModel, type[HeaderModel]]] = None,
        response_wrapper: Optional[ResponseWrapper] = None,
        status_code: Optional[int] = None,
        tags: Optional[list[Union[str, Enum]]] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        response_description: str = "Successful Response",
        responses: Optional[dict[Union[int, str], dict[str, Any]]] = None,
        deprecated: Optional[bool] = None,
        operation_id: Optional[str] = None,
        response_model_include: Optional[IncEx] = None,
        response_model_exclude: Optional[IncEx] = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        openapi_extra: Optional[dict[str, Any]] = None,
    ) -> Router: ...

    def WS(self, path: str = "", *, handle_data: list[str] = [], **kwargs: dict[str, Any]):
        router = Router(self, ["WS"], path, handle=WsHandle(handle_data), **kwargs)
        self.pending_routers.append(router)
        return router
