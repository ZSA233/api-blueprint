from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any, DefaultDict, Literal, Optional, Self, Union

from fastapi import FastAPI

from api_blueprint.engine.connection import (
    ConnectionDelivery,
    ConnectionKind,
    ConnectionScope,
    DefaultConnectionClose,
    MessageContract,
    ModelRef,
    ensure_model_ref,
    normalize_message_contract,
)
from api_blueprint.engine.binary_schema import BinarySchema, load_binary_schema, resolve_schema_path
from api_blueprint.engine.runtime import (
    Handle,
    Provider,
    ProviderName,
    ResponseEnvelope,
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


METHOD_ENUM = Literal["GET", "POST", "PUT", "DELETE", "HEAD", "WS", "STREAM", "CHANNEL"]
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
    req_binary_schema: Optional[BinarySchema]

    rsp_model: Optional[Model]
    rsp_envelope: Optional[ResponseEnvelope]

    recvs: list[Model]
    sends: list[Model]
    connection_kind: ConnectionKind
    connection_delivery: ConnectionDelivery | None
    connection_scope: ConnectionScope | None
    open_model: ModelRef | None
    close_model: ModelRef | None
    server_message: MessageContract | None
    client_message: MessageContract | None

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
        response_envelope: Optional[ResponseEnvelope] = None,
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
        self.req_binary_schema = None
        self.rsp_model = None

        if "response_wrapper" in kwargs:
            raise TypeError("response_wrapper is removed; use response_envelope")
        self.rsp_envelope = response_envelope
        self._headers = headers

        self._handle = handle
        self._providers = providers
        self._tags = tags

        self.is_deprecated = False
        self.rsp_media_type = "application/json"

        self.errors = defaultdict(list)
        self.recvs = []
        self.sends = []
        self.connection_kind = self._infer_connection_kind(methods)
        self.connection_scope = self._normalize_connection_scope(kwargs.pop("scope", None))
        self.connection_delivery = self._normalize_connection_delivery(kwargs.pop("delivery", None))
        self.open_model = None
        self.close_model = None
        self.server_message = None
        self.client_message = None
        if self.connection_kind in {ConnectionKind.STREAM, ConnectionKind.CHANNEL}:
            self.connection_scope = self.connection_scope or ConnectionScope.SESSION
            self.connection_delivery = self.connection_delivery or ConnectionDelivery.ORDERED

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
    def response_envelope(self) -> type[ResponseEnvelope]:
        response_envelope = self.rsp_envelope
        if response_envelope is None:
            response_envelope = self.bp.response_envelope
        return response_envelope

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
        self._reject_if_binary_schema("REQ_JSON")
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
        self._reject_if_binary_schema("REQ_FORM")
        if __model is None:
            __model = create_model(f"REQ_{self.name}_FORM", kwargs)

        if isinstance(__model, Model):
            __model = __model.__class__
        elif isinstance(__model, Field):
            __model = create_field_wrapped_model(f"REQ_{self.name}_FORM", __model)
        self.req_form = __model
        return self

    def REQ_BIN(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Self:
        raise ValueError("REQ_BIN(Model) is removed; use REQ_BINARY(path)")

    def REQ_BINARY(self, schema: str | BinarySchema) -> Self:
        if self.req_json is not None or self.req_form is not None or self.req_bin is not None:
            raise ValueError("REQ_BINARY() cannot be combined with REQ/REQ_JSON/REQ_FORM/REQ_BIN")
        if self.req_binary_schema is not None:
            raise ValueError("REQ_BINARY() can only be called once")
        self.req_binary_schema = schema if isinstance(schema, BinarySchema) else load_binary_schema(resolve_schema_path(schema))
        self._attach_binary_openapi()
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

    def RAW_RESPONSE(self) -> Self:
        self.extra["http_raw_response"] = True
        return self

    def HTTP_RAW_RESPONSE(self) -> Self:
        self.extra["http_raw_response"] = True
        return self

    async def upstream_handler(self, request: "Request", **kwargs: Any):
        return await proxy_upstream_request(self, request, **kwargs)

    def do_register(self, app: FastAPI) -> None:
        self.validate_connection_contract()
        register_router(self, app)

    def RECV(self, *models: list[Model]) -> Self:
        self.recvs.extend(models)
        return self

    def SEND(self, *models: list[Model]) -> Self:
        self.sends.extend(models)
        return self

    def OPEN(self, model: ModelRef) -> Self:
        if self.connection_kind not in {ConnectionKind.STREAM, ConnectionKind.CHANNEL}:
            raise ValueError("OPEN() is only supported by STREAM() and CHANNEL() routes")
        if self.open_model is not None:
            raise ValueError("OPEN() can only be called once")
        self.open_model = ensure_model_ref(model, label="OPEN() model")
        return self

    def CLOSE(self, model: ModelRef) -> Self:
        if self.connection_kind not in {ConnectionKind.STREAM, ConnectionKind.CHANNEL}:
            raise ValueError("CLOSE() is only supported by STREAM() and CHANNEL() routes")
        if self.close_model is not None:
            raise ValueError("CLOSE() can only be called once")
        self.close_model = ensure_model_ref(model, label="CLOSE() model")
        return self

    def SERVER_MESSAGE(self, *args: object, **variants: ModelRef) -> Self:
        if self.connection_kind not in {ConnectionKind.STREAM, ConnectionKind.CHANNEL}:
            raise ValueError("SERVER_MESSAGE() is only supported by STREAM() and CHANNEL() routes")
        if self.server_message is not None:
            raise ValueError("SERVER_MESSAGE() can only be called once")
        self.server_message = normalize_message_contract(args, variants)
        return self

    def CLIENT_MESSAGE(self, *args: object, **variants: ModelRef) -> Self:
        if self.connection_kind == ConnectionKind.STREAM:
            raise ValueError("STREAM() routes do not support CLIENT_MESSAGE()")
        if self.connection_kind != ConnectionKind.CHANNEL:
            raise ValueError("CLIENT_MESSAGE() is only supported by CHANNEL() routes")
        if self.client_message is not None:
            raise ValueError("CLIENT_MESSAGE() can only be called once")
        self.client_message = normalize_message_contract(args, variants)
        return self

    def validate_connection_contract(self) -> None:
        if self.connection_kind == ConnectionKind.STREAM:
            if self.server_message is None:
                raise ValueError(f"STREAM route[{self.url}] requires SERVER_MESSAGE()")
            if self.client_message is not None:
                raise ValueError(f"STREAM route[{self.url}] must not define CLIENT_MESSAGE()")
            self._reject_http_body_contracts()
        elif self.connection_kind == ConnectionKind.CHANNEL:
            if self.server_message is None:
                raise ValueError(f"CHANNEL route[{self.url}] requires SERVER_MESSAGE()")
            if self.client_message is None:
                raise ValueError(f"CHANNEL route[{self.url}] requires CLIENT_MESSAGE()")
            self._reject_http_body_contracts()

    def _reject_http_body_contracts(self) -> None:
        if (
            self.req_json is not None
            or self.req_form is not None
            or self.req_bin is not None
            or self.req_binary_schema is not None
            or self.rsp_model is not None
        ):
            raise ValueError(
                f"{self.connection_kind.value.upper()} route[{self.url}] uses OPEN/SERVER_MESSAGE/CLIENT_MESSAGE/CLOSE "
                "instead of REQ_JSON/REQ_FORM/REQ_BINARY/RSP"
            )

    @property
    def effective_close_model(self) -> ModelRef | None:
        if self.connection_kind in {ConnectionKind.STREAM, ConnectionKind.CHANNEL}:
            return self.close_model or DefaultConnectionClose
        return self.close_model

    @staticmethod
    def _infer_connection_kind(methods: list[METHOD_ENUM]) -> ConnectionKind:
        if any(method == "STREAM" for method in methods):
            return ConnectionKind.STREAM
        if any(method == "CHANNEL" for method in methods):
            return ConnectionKind.CHANNEL
        if any(method == "WS" for method in methods):
            return ConnectionKind.LEGACY_WS
        return ConnectionKind.RPC

    @staticmethod
    def _normalize_connection_scope(value: object) -> ConnectionScope | None:
        if value is None:
            return None
        if isinstance(value, ConnectionScope):
            return value
        return ConnectionScope(str(value))

    @staticmethod
    def _normalize_connection_delivery(value: object) -> ConnectionDelivery | None:
        if value is None:
            return None
        if isinstance(value, ConnectionDelivery):
            return value
        return ConnectionDelivery(str(value))

    def _reject_if_binary_schema(self, method: str) -> None:
        if self.req_binary_schema is not None:
            raise ValueError(f"{method}() cannot be combined with REQ_BINARY()")

    def _attach_binary_openapi(self) -> None:
        schema = self.req_binary_schema
        if schema is None:
            return
        extra = dict(self.extra.get("openapi_extra") or {})
        request_body = dict(extra.get("requestBody") or {})
        content = dict(request_body.get("content") or {})
        content[schema.content_type] = {"schema": {"type": "string", "format": "binary"}}
        request_body["content"] = content
        extra["requestBody"] = request_body
        extra["x-api-blueprint-binary-schema"] = schema.to_route_manifest()
        self.extra["openapi_extra"] = extra
