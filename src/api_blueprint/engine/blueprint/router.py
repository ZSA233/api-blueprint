from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from enum import Enum
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
    Array,
    Error,
    Field,
    FileField,
    HeaderModel,
    Map,
    Model,
    OneOf,
    create_field_wrapped_model,
    create_model,
    iter_model_vars,
    unwrap_errors,
)
from api_blueprint.engine.utils import join_url_path, snake_to_pascal_case

if TYPE_CHECKING:
    from fastapi import Request

    from api_blueprint.engine.blueprint.group import RouterGroup


METHOD_ENUM = Literal["GET", "POST", "PUT", "DELETE", "HEAD", "STREAM", "CHANNEL"]
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
    req_urlencoded: Optional[Model]
    req_multipart: Optional[Model]
    req_bin: Optional[Model]
    req_json: Optional[Model]
    req_binary_schema: Optional[BinarySchema]

    rsp_model: Optional[Model]
    rsp_binary_schema: Optional[BinarySchema]
    rsp_envelope: Optional[ResponseEnvelope]
    rsp_kind: str

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
        self.req_urlencoded = None
        self.req_multipart = None
        self.req_json = None
        self.req_bin = None
        self.req_binary_schema = None
        self.rsp_model = None
        self.rsp_binary_schema = None

        if "response_wrapper" in kwargs:
            raise TypeError("response_wrapper is removed; use response_envelope")
        self.rsp_envelope = response_envelope
        self._headers = headers

        self._handle = handle
        self._providers = providers
        self._tags = tags

        self.is_deprecated = False
        self.rsp_kind = "json"
        self.rsp_media_type = "application/json"
        self.rsp_filename = None

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
        tags: list[str] = []
        seen: set[str] = set()
        route_tags = self._tags or []
        for tag in (*route_tags, *self.bp.tags):
            value = str(tag.value if isinstance(tag, Enum) else tag)
            if value in seen:
                continue
            tags.append(value)
            seen.add(value)
        return list(tags)

    def ARGS(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Self:
        if __model is None:
            __model = create_model(f"REQ_{self.name}_QUERY", kwargs)

        if isinstance(__model, Model):
            __model = __model.__class__
        elif isinstance(__model, Field):
            __model = create_field_wrapped_model(f"REQ_{self.name}_QUERY", __model)
        self._reject_file_fields(__model, "ARGS")
        self.req_query = __model
        return self

    def REQ_JSON(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Self:
        self._reject_if_body_contract("REQ_JSON")
        self.req_json = self._normalize_request_model(f"REQ_{self.name}_JSON", __model, kwargs)
        self._reject_file_fields(self.req_json, "REQ_JSON")
        return self

    def REQ(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Self:
        return self.REQ_JSON(__model, **kwargs)

    def REQ_FORM(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Self:
        return self.REQ_URLENCODED(__model, **kwargs)

    def REQ_URLENCODED(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Self:
        self._reject_if_body_contract("REQ_URLENCODED")
        model = self._normalize_request_model(f"REQ_{self.name}_FORM", __model, kwargs)
        self._reject_file_fields(model, "REQ_URLENCODED")
        self.req_urlencoded = model
        self.req_form = model
        return self

    def REQ_MULTIPART(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Self:
        self._reject_if_body_contract("REQ_MULTIPART")
        model = self._normalize_request_model(f"REQ_{self.name}_MULTIPART", __model, kwargs)
        self.req_multipart = model
        self._attach_multipart_openapi()
        return self

    def REQ_BIN(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Self:
        raise ValueError("REQ_BIN(Model) is removed; use REQ_BINARY(path)")

    def REQ_BINARY_SCHEMA(self, schema: str | BinarySchema, *, content_type: str | None = None) -> Self:
        self._reject_if_body_contract("REQ_BINARY_SCHEMA")
        if self.req_binary_schema is not None:
            raise ValueError("REQ_BINARY_SCHEMA() can only be called once")
        self.req_binary_schema = self._normalize_binary_schema(schema, content_type=content_type)
        self._attach_binary_openapi()
        return self

    def REQ_BINARY(self, schema: str | BinarySchema, *, content_type: str | None = None) -> Self:
        return self.REQ_BINARY_SCHEMA(schema, content_type=content_type)

    def _RSP_AS_MODEL(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Optional[Model]:
        if __model is None:
            __model = create_model(f"RSP_{self.name}", kwargs)

        if isinstance(__model, Model):
            __model = __model.__class__
        elif isinstance(__model, Field):
            __model = create_field_wrapped_model(f"RSP_{self.name}", __model)
        return __model

    def RSP_JSON(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Self:
        self._reject_if_raw_response_contract("RSP_JSON")
        self._reject_if_http_raw_response("RSP_JSON")
        self.rsp_model = self._RSP_AS_MODEL(__model, **kwargs)
        self._reject_file_fields(self.rsp_model, "RSP_JSON")
        self.rsp_kind = "json"
        self.rsp_media_type = "application/json"
        return self

    def RSP(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Self:
        return self.RSP_JSON(__model, **kwargs)

    def RSP_EMPTY(self) -> Self:
        self._reject_if_raw_response_contract("RSP_EMPTY")
        self._reject_if_http_raw_response("RSP_EMPTY")
        self.rsp_model = self._RSP_AS_MODEL()
        self.rsp_kind = "json"
        self.rsp_media_type = "application/json"
        return self

    def RSP_XML(self, __model: Optional[Model] = None, **kwargs: dict[str, ModelOrField]) -> Self:
        self._reject_if_raw_response_contract("RSP_XML")
        self._reject_if_http_raw_response("RSP_XML")
        self.rsp_model = self._RSP_AS_MODEL(__model, **kwargs)
        self._reject_file_fields(self.rsp_model, "RSP_XML")
        self.rsp_kind = "xml"
        self.rsp_media_type = "application/xml"
        return self

    def RSP_BYTES(self, *, content_type: str = "application/octet-stream") -> Self:
        return self._raw_response("bytes", content_type=content_type)

    def RSP_FILE(
        self,
        *,
        content_type: str = "application/octet-stream",
        default_filename: str | None = None,
        filename: str | None = None,
    ) -> Self:
        if default_filename is not None and filename is not None and default_filename != filename:
            raise ValueError("RSP_FILE() filename and default_filename must match when both are provided")
        self.rsp_filename = default_filename if default_filename is not None else filename
        return self._raw_response("file", content_type=content_type)

    def RSP_BYTE_STREAM(self, *, content_type: str = "application/octet-stream") -> Self:
        return self._raw_response("byte_stream", content_type=content_type)

    def RSP_BINARY_SCHEMA(self, schema: str | BinarySchema, *, content_type: str | None = None) -> Self:
        self._reject_if_raw_response_contract("RSP_BINARY_SCHEMA")
        self._reject_if_http_raw_response("RSP_BINARY_SCHEMA")
        if self.rsp_model is not None:
            raise ValueError("RSP_BINARY_SCHEMA() cannot be combined with RSP/RSP_JSON/RSP_EMPTY/RSP_XML")
        self.rsp_binary_schema = self._normalize_binary_schema(schema, content_type=content_type)
        self.rsp_model = None
        self.rsp_kind = "binary_schema"
        self.rsp_media_type = self.rsp_binary_schema.content_type
        self.rsp_envelope = None
        self._attach_binary_response_openapi()
        return self

    def RSP_BINARY(self, schema: str | BinarySchema, *, content_type: str | None = None) -> Self:
        return self.RSP_BINARY_SCHEMA(schema, content_type=content_type)

    def ERR(self, *errors: Union[Error, Model]) -> Self:
        self.errors = unwrap_errors(list(errors))
        return self

    def DEPRECATED(self) -> Self:
        self.is_deprecated = True
        return self

    def RAW_RESPONSE(self) -> Self:
        if self.rsp_kind != "json":
            raise ValueError("RAW_RESPONSE() can only be applied to JSON response contracts")
        self.extra["http_raw_response"] = True
        return self

    def HTTP_RAW_RESPONSE(self) -> Self:
        if self.rsp_kind != "json":
            raise ValueError("HTTP_RAW_RESPONSE() can only be applied to JSON response contracts")
        self.extra["http_raw_response"] = True
        return self

    async def upstream_handler(self, request: "Request", **kwargs: Any):
        return await proxy_upstream_request(self, request, **kwargs)

    def do_register(self, app: FastAPI) -> None:
        self.validate_connection_contract()
        register_router(self, app)

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
            or self.req_urlencoded is not None
            or self.req_multipart is not None
            or self.req_bin is not None
            or self.req_binary_schema is not None
            or self.rsp_model is not None
            or self.rsp_kind in {"bytes", "file", "byte_stream", "binary_schema"}
        ):
            raise ValueError(
                f"{self.connection_kind.value.upper()} route[{self.url}] uses OPEN/SERVER_MESSAGE/CLIENT_MESSAGE/CLOSE "
                "instead of REQ_JSON/REQ_URLENCODED/REQ_MULTIPART/REQ_BINARY/RSP"
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

    @property
    def request_body_kind(self) -> str:
        if self.req_json is not None:
            return "json"
        if self.req_multipart is not None:
            return "multipart"
        if self.req_urlencoded is not None:
            return "urlencoded"
        if self.req_binary_schema is not None:
            return "binary_schema"
        if self.req_bin is not None:
            return "raw_bytes"
        return "none"

    @property
    def response_kind(self) -> str:
        return self.rsp_kind

    def _normalize_request_model(
        self,
        name: str,
        model: Optional[Model],
        kwargs: dict[str, ModelOrField],
    ) -> Model:
        if model is None:
            model = create_model(name, kwargs)
        if isinstance(model, Model):
            return model.__class__
        if isinstance(model, Field):
            return create_field_wrapped_model(name, model)
        return model

    def _normalize_binary_schema(
        self,
        schema: str | BinarySchema,
        *,
        content_type: str | None = None,
    ) -> BinarySchema:
        resolved = schema if isinstance(schema, BinarySchema) else load_binary_schema(resolve_schema_path(schema))
        media_type = (content_type or "").strip()
        if not media_type:
            return resolved
        return replace(resolved, content_type=media_type)

    def _reject_if_body_contract(self, method: str) -> None:
        if self.request_body_kind != "none":
            existing = "REQ_BINARY" if self.request_body_kind == "binary_schema" else self.request_body_kind
            raise ValueError(f"{method}() cannot be combined with {existing} request body")

    def _reject_if_raw_response_contract(self, method: str) -> None:
        if self.rsp_kind in {"bytes", "file", "byte_stream", "binary_schema"}:
            raise ValueError(f"{method}() cannot be combined with {self.rsp_kind} response")

    def _reject_if_http_raw_response(self, method: str) -> None:
        if self.extra.get("http_raw_response"):
            raise ValueError(f"{method}() cannot be combined with HTTP_RAW_RESPONSE()")

    def _raw_response(self, kind: str, *, content_type: str) -> Self:
        self._reject_if_http_raw_response(f"RSP_{kind.upper()}")
        if self.rsp_model is not None:
            raise ValueError(f"RSP_{kind.upper()}() cannot be combined with RSP/RSP_JSON/RSP_EMPTY/RSP_XML")
        if self.rsp_binary_schema is not None:
            raise ValueError(f"RSP_{kind.upper()}() cannot be combined with RSP_BINARY_SCHEMA")
        media_type = content_type.strip() or "application/octet-stream"
        self.rsp_model = None
        self.rsp_binary_schema = None
        self.rsp_kind = kind
        self.rsp_media_type = media_type
        self.rsp_envelope = None
        self._attach_raw_response_openapi()
        return self

    def _reject_file_fields(self, model: Model | None, method: str) -> None:
        if model is None:
            return
        for field_path in _iter_file_field_paths(model):
            raise ValueError(f"{method}() cannot use FileField field {field_path!r}; use REQ_MULTIPART()")

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

    def _attach_multipart_openapi(self) -> None:
        model = self.req_multipart
        if model is None:
            return
        extra = dict(self.extra.get("openapi_extra") or {})
        request_body = dict(extra.get("requestBody") or {})
        properties: dict[str, Any] = {}
        required: list[str] = []
        for field_name, field_value in iter_model_vars(model):
            if not isinstance(field_value, Field):
                continue
            field_extra = dict(getattr(field_value, "__extra__", {}) or {})
            wire_name = str(field_extra.get("alias") or field_name)
            field_schema: dict[str, Any]
            if isinstance(field_value, FileField):
                field_schema = {"type": "string", "format": "binary"}
                content_types = field_extra.get("content_types")
                if content_types:
                    field_schema["x-content-types"] = list(content_types)
                if field_extra.get("max_size") is not None:
                    field_schema["x-max-size"] = int(field_extra["max_size"])
            else:
                field_schema = {"type": "string"}
            description = field_extra.get("description")
            if description:
                field_schema["description"] = str(description)
            properties[wire_name] = field_schema
            if not bool(field_extra.get("optional") or field_extra.get("omitempty")):
                required.append(wire_name)
        schema: dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        request_body["content"] = {
            **dict(request_body.get("content") or {}),
            "multipart/form-data": {"schema": schema},
        }
        extra["requestBody"] = request_body
        self.extra["openapi_extra"] = extra

    def _attach_raw_response_openapi(self) -> None:
        extra = dict(self.extra.get("openapi_extra") or {})
        responses = dict(extra.get("responses") or {})
        response = dict(responses.get("200") or {})
        response["description"] = response.get("description") or "Raw response"
        response["content"] = {
            **dict(response.get("content") or {}),
            self.rsp_media_type: {"schema": {"type": "string", "format": "binary"}},
        }
        if self.rsp_kind == "file":
            headers = dict(response.get("headers") or {})
            headers["Content-Disposition"] = {
                "description": "File download disposition",
                "schema": {"type": "string"},
            }
            response["headers"] = headers
        responses["200"] = response
        extra["responses"] = responses
        self.extra["openapi_extra"] = extra

    def _attach_binary_response_openapi(self) -> None:
        schema = self.rsp_binary_schema
        if schema is None:
            return
        extra = dict(self.extra.get("openapi_extra") or {})
        responses = dict(extra.get("responses") or {})
        response = dict(responses.get("200") or {})
        response["description"] = response.get("description") or "Binary schema response"
        content = dict(response.get("content") or {})
        content[schema.content_type] = {
            "schema": {"type": "string", "format": "binary"},
            "x-binary-schema": schema.to_route_manifest(),
        }
        response["content"] = content
        response["x-api-blueprint-binary-schema"] = schema.to_route_manifest()
        responses["200"] = response
        extra["responses"] = responses
        self.extra["openapi_extra"] = extra


def _iter_file_field_paths(model: Model | type[Model], prefix: str = "", seen: set[int] | None = None):
    seen = seen or set()
    model_id = id(model)
    if model_id in seen:
        return
    seen.add(model_id)
    for field_name, field_value in iter_model_vars(model):
        path = f"{prefix}.{field_name}" if prefix else field_name
        yield from _iter_file_field_value_paths(field_value, path, seen)


def _iter_file_field_value_paths(field_value: Any, path: str, seen: set[int]):
    if isinstance(field_value, FileField):
        yield path
        return
    if isinstance(field_value, OneOf):
        for index, variant in enumerate(field_value.variants):
            yield from _iter_file_field_value_paths(variant, f"{path}<variant{index}>", seen)
        return
    if isinstance(field_value, Array):
        yield from _iter_file_field_value_paths(field_value.elem_type(), f"{path}[]", seen)
        return
    if isinstance(field_value, Map):
        yield from _iter_file_field_value_paths(field_value.value_type(), f"{path}{{}}", seen)
        return
    if isinstance(field_value, Model) or (isinstance(field_value, type) and issubclass(field_value, Model)):
        yield from _iter_file_field_paths(field_value, path, seen)
