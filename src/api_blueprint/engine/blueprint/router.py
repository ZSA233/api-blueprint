from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any, DefaultDict, Literal, Optional, Self, Union

from fastapi import FastAPI

from api_blueprint.engine.runtime import (
    Handle,
    Provider,
    ProviderName,
    ResponseWrapper,
    ellipsis_replaces,
    proxy_upstream_request,
    register_router,
)
from api_blueprint.engine.schema import (
    Error,
    Field,
    HeaderModel,
    Model,
    create_field_wrapped_model,
    create_model,
    unwrap_errors,
)
from api_blueprint.engine.utils import join_url_path, snake_to_pascal_case

if TYPE_CHECKING:
    from fastapi import Request

    from api_blueprint.engine.blueprint.group import RouterGroup


METHOD_ENUM = Literal["GET", "POST", "PUT", "DELETE", "HEAD", "WS"]
ModelOrField = Union[Model, Field]


class ConflictFieldError(Exception):
    pass


class Router:
    group: "RouterGroup"

    leaf: str
    methods: list[METHOD_ENUM]
    medio_type: str

    req_query: Optional[Model]
    req_form: Optional[Model]
    req_bin: Optional[Model]
    req_json: Optional[Model]

    rsp_model: Optional[Model]
    rsp_wrapper: Optional[ResponseWrapper]

    recvs: list[Model]
    sends: list[Model]

    errors: DefaultDict[int, list[Error]]
    extra: dict[str, Any]

    _handle: Provider = Handle
    _providers: Optional[list[Provider]]
    _tags: Optional[list[str]] = None
    is_deprecated: bool = False

    def __init__(
        self,
        group: "RouterGroup",
        methods: list[METHOD_ENUM],
        api: str,
        response_wrapper: Optional[ResponseWrapper] = None,
        headers: Optional[Union[HeaderModel, type[HeaderModel]]] = None,
        providers: Optional[list[Provider]] = None,
        tags: Optional[list[str]] = None,
        *,
        handle: Provider = Handle,
        **kwargs: dict[str, Any],
    ):
        self.group = group
        self.leaf = api
        self.methods = methods
        self.extra = kwargs

        self.req_query = None
        self.req_form = None
        self.req_json = None
        self.req_bin = None
        self.rsp_model = None

        self.rsp_wrapper = response_wrapper
        self._headers = headers

        self._handle = handle
        self._providers = providers
        self._tags = tags

        self.is_deprecated = False
        self.rsp_media_type = "application/json"

        self.errors = defaultdict(list)
        self.recvs = []
        self.sends = []

    def __str__(self) -> str:
        return f"<Router {self.methods} - {self.url} >"

    @property
    def url(self) -> str:
        return join_url_path(self.group.prefix, self.leaf)

    @property
    def root(self):
        return self.group.root

    @property
    def bp(self):
        return self.group.bp

    @property
    def name(self) -> str:
        return snake_to_pascal_case(self.leaf)

    @property
    def providers(self) -> list[Provider]:
        providers = self._providers
        if providers is not None:
            providers = ellipsis_replaces(self.bp.providers, self._providers)
        else:
            providers = self.bp.providers

        remap_providers = []
        for provider in providers:
            if provider.name == ProviderName.HANDLE.value:
                provider = self._handle
            remap_providers.append(provider)
        return remap_providers

    @property
    def headers(self) -> Optional[HeaderModel]:
        return self._headers or self.bp.headers

    @property
    def response_wrapper(self) -> type[ResponseWrapper]:
        response_wrapper = self.rsp_wrapper
        if response_wrapper is None:
            response_wrapper = self.bp.response_wrapper
        return response_wrapper

    @property
    def tags(self) -> list[str]:
        tags = set()
        if self._tags is not None:
            tags.update(self._tags)
        if self.bp.tags:
            tags.update(self.bp.tags)
        return list(tags)

    def ARGS(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Self:
        if __model is None:
            __model = create_model(f"REQ_{self.name}_QUERY", kwargs)

        if isinstance(__model, Model):
            __model = __model.__class__
        elif isinstance(__model, Field):
            __model = create_field_wrapped_model(f"REQ_{self.name}_QUERY", __model)
        self.req_query = __model
        return self

    def REQ_JSON(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Self:
        if __model is None:
            __model = create_model(f"REQ_{self.name}_JSON", kwargs)

        if isinstance(__model, Model):
            __model = __model.__class__
        elif isinstance(__model, Field):
            __model = create_field_wrapped_model(f"REQ_{self.name}_JSON", __model)
        self.req_json = __model
        return self

    def REQ(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Self:
        return self.REQ_JSON(__model, **kwargs)

    def REQ_FORM(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Self:
        if __model is None:
            __model = create_model(f"REQ_{self.name}_FORM", kwargs)

        if isinstance(__model, Model):
            __model = __model.__class__
        elif isinstance(__model, Field):
            __model = create_field_wrapped_model(f"REQ_{self.name}_FORM", __model)
        self.req_form = __model
        return self

    def REQ_BIN(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Self:
        if __model is None:
            __model = create_model(f"REQ_{self.name}_BIN", kwargs)

        if isinstance(__model, Model):
            __model = __model.__class__
        elif isinstance(__model, Field):
            __model = create_field_wrapped_model(f"REQ_{self.name}_BIN", __model)
        self.req_bin = __model
        return self

    def _RSP_AS_MODEL(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Optional[Model]:
        if __model is None:
            __model = create_model(f"RSP_{self.name}", kwargs)

        if isinstance(__model, Model):
            __model = __model.__class__
        elif isinstance(__model, Field):
            __model = create_field_wrapped_model(f"RSP_{self.name}", __model)
        return __model

    def RSP_JSON(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Self:
        self.rsp_model = self._RSP_AS_MODEL(__model, **kwargs)
        self.rsp_media_type = "application/json"
        return self

    def RSP(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Self:
        return self.RSP_JSON(__model, **kwargs)

    def RSP_XML(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Self:
        self.rsp_model = self._RSP_AS_MODEL(__model, **kwargs)
        self.rsp_media_type = "application/xml"
        return self

    def ERR(self, *errors: Union[Error, Model]) -> Self:
        self.errors = unwrap_errors(list(errors))
        return self

    def DEPRECATED(self) -> Self:
        self.is_deprecated = True
        return self

    async def upstream_handler(self, request: "Request", **kwargs: Any):
        return await proxy_upstream_request(self, request, **kwargs)

    def do_register(self, app: FastAPI) -> None:
        register_router(self, app)

    def RECV(self, *models: list[Model]) -> Self:
        self.recvs.extend(models)
        return self

    def SEND(self, *models: list[Model]) -> Self:
        self.sends.extend(models)
        return self
