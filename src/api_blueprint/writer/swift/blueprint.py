from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional, Type, Union, get_origin

from api_blueprint.engine.connection import MessageContract
from api_blueprint.engine.model import FieldWrappedModel, Model, iter_field_model_type, unwrap_model_type
from api_blueprint.engine.router import Router
from api_blueprint.writer.core.base import BaseBlueprint
from api_blueprint.writer.core.contract_adapters import RouteProtocolContract, route_protocol_from_router

from .binary_schema import SwiftBinarySchema, unique_swift_binary_schemas
from .naming import to_swift_identifier, to_swift_path, to_swift_type_name
from .protos import SwiftProto, SwiftProtoRegistry, SwiftResolvedType


@dataclass(frozen=True)
class SwiftMessageRef:
    name: str


@dataclass(frozen=True)
class SwiftMessageVariant:
    key: str
    case_name: str
    static_name: str
    data_type: str


@dataclass(frozen=True)
class SwiftMessageHelper:
    name: str
    variants: tuple[SwiftMessageVariant, ...]


class SwiftRoute:
    def __init__(
        self,
        router: Router,
        registry: SwiftProtoRegistry,
        *,
        protocol: RouteProtocolContract | None = None,
    ):
        self.router = router
        self.registry = registry
        self.protocol = protocol or route_protocol_from_router(router)
        self.func_name = self.protocol.route.func_name
        self.method_name = to_swift_identifier(self.func_name)
        self.group_slug = self.protocol.route.group_slug
        self.group_class = to_swift_type_name(self.group_slug, fallback="Root") + "API"
        self.url = self.protocol.route.url
        self.http_methods = list(self.protocol.route.http_methods)
        self.supports_stream = self.protocol.route.supports_stream
        self.supports_channel = self.protocol.route.supports_channel
        if self.is_rpc and len(self.http_methods) != 1:
            raise ValueError(f"[swift-client] Swift 客户端要求每个 route 只有一个 HTTP method: {self.url}")

        self.path_proto = self._ensure_model(self.protocol.request.path.model, "Path")
        self.query_proto = self._ensure_model(self.protocol.request.query.model, "Query")
        self.open_proto = self._ensure_model(self.protocol.request.open.model, "Open")
        self.form_proto = self._ensure_model(self.protocol.request.form.model, "Form")
        self.multipart_proto = self._ensure_model(self.protocol.request.multipart.model, "Form")
        self.json_proto = self._ensure_model(self.protocol.request.json.model, "JSON")
        self.binary_schema = self.protocol.request.binary_schema
        self.binary_proto = None if self.binary_schema is not None else self._ensure_model(
            self.protocol.request.binary.model, "Binary"
        )
        self.response_kind = self.protocol.response.kind
        self.response_media_type = self.protocol.response.media_type
        self.response_binary_schema = self.protocol.response.binary_schema
        self.response_payload_proto = self._ensure_model(self.protocol.response.model.model, "Response")
        self.response_type = self._payload_response_type()
        self.server_message_proto = self._ensure_message_contract(self.protocol.server_message, "ServerMessage")
        self.client_message_proto = self._ensure_message_contract(self.protocol.client_message, "ClientMessage")
        self.close_proto = self._ensure_model(self.protocol.close_model, "Close")
        self._message_helpers = self._build_message_helpers()

    @property
    def is_rpc(self) -> bool:
        return not (self.supports_stream or self.supports_channel)

    @property
    def http_method(self) -> str:
        return self.http_methods[0] if self.http_methods else "GET"

    @property
    def request_body_kind(self) -> str:
        return self.protocol.request.body_kind

    @property
    def query_type(self) -> str | None:
        return self.query_proto.name if self.query_proto else None

    @property
    def path_type(self) -> str | None:
        return self.path_proto.name if self.path_proto else None

    @property
    def open_type(self) -> str | None:
        return self.open_proto.name if self.open_proto else None

    @property
    def json_type(self) -> str | None:
        return self.json_proto.name if self.json_proto else None

    @property
    def form_type(self) -> str | None:
        return self.form_proto.name if self.form_proto else None

    @property
    def multipart_type(self) -> str | None:
        return self.multipart_proto.name if self.multipart_proto else None

    @property
    def binary_type(self) -> str | None:
        if self.binary_schema is not None:
            return self.swift_binary_schema.name
        return self.binary_proto.name if self.binary_proto else None

    @property
    def swift_binary_schema(self) -> SwiftBinarySchema:
        if self.binary_schema is None:
            raise RuntimeError("route has no binary schema")
        return SwiftBinarySchema(self.binary_schema)

    @property
    def has_binary_schema(self) -> bool:
        return self.binary_schema is not None

    @property
    def has_response_binary_schema(self) -> bool:
        return self.response_binary_schema is not None

    @property
    def response_binary_schema_obj(self) -> SwiftBinarySchema | None:
        if self.response_binary_schema is None:
            return None
        return SwiftBinarySchema(self.response_binary_schema)

    @property
    def binary_param_name(self) -> str:
        return to_swift_identifier(self.func_name)

    @property
    def server_message_type(self) -> str:
        return self.server_message_proto.name if self.server_message_proto else "APIJSONValue"

    @property
    def client_message_type(self) -> str:
        return self.client_message_proto.name if self.client_message_proto else "APIJSONValue"

    @property
    def close_type(self) -> str:
        return self.close_proto.name if self.close_proto else "APISocketCloseInfo"

    @property
    def subscribe_method_name(self) -> str:
        return to_swift_identifier(
            self.protocol.route.stream.connect_method if self.protocol.route.stream else f"subscribe{self.func_name}"
        )

    @property
    def open_channel_method_name(self) -> str:
        return to_swift_identifier(
            self.protocol.route.channel.connect_method if self.protocol.route.channel else f"open{self.func_name}"
        )

    @property
    def connection_delivery(self) -> str:
        if self.protocol.route.channel is None or self.protocol.route.channel.delivery is None:
            return "ordered"
        return self.protocol.route.channel.delivery.value

    @property
    def response_envelope_literal(self) -> str:
        spec = self.protocol.response.envelope.envelope_spec()
        fields = spec.get("fields") if isinstance(spec.get("fields"), dict) else {}
        return (
            "APIResponseEnvelope("
            f"name: {json.dumps(spec.get('name') or 'NoEnvelope')}, "
            f"kind: {json.dumps(spec.get('kind') or 'none')}, "
            f"errorIdentity: {json.dumps(spec.get('error_identity') or 'none')}, "
            f"successCode: {int(spec.get('success_code') or 0)}, "
            f"successMessage: {json.dumps(spec.get('success_message') or 'ok')}, "
            "fields: APIResponseEnvelopeFields("
            f"code: {json.dumps(fields.get('code') or 'code')}, "
            f"message: {json.dumps(fields.get('message') or 'message')}, "
            f"data: {json.dumps(fields.get('data') or 'data')}, "
            f"error: {json.dumps(fields.get('error') or 'error')}, "
            f"ok: {json.dumps(fields.get('ok') or 'ok')}"
            ")"
            ")"
        )

    @property
    def decoder_expr(self) -> str:
        if self.response_kind in {"bytes", "file"}:
            return "{ value in try apiDecodeRawResponse(value) }"
        if self.response_kind == "byte_stream":
            return "{ value in try apiDecodeStreamResponse(value) }"
        if self.response_kind == "binary_schema" and self.response_binary_schema_obj is not None:
            return "{ value in try " + self.response_binary_schema_obj.decode_func + "(try apiDecodeData(value)) }"
        if self.response_media_type != "application/json":
            return "{ value in try apiDecodeString(value) }"
        if self.response_payload_proto is None:
            return "{ _ in () }"
        return "{ value in try apiDecodeValue(" + self.response_type.text + ".self, from: value) }"

    @property
    def data_decoder_expr(self) -> str:
        if self.response_kind in {"bytes", "file", "byte_stream"}:
            return '{ _, _, _ in throw APIDecodeError.invalidResponse("response is decoded from transport metadata") }'
        if self.response_kind == "binary_schema" and self.response_binary_schema_obj is not None:
            return "{ data, _, _ in try " + self.response_binary_schema_obj.decode_func + "(data) }"
        if self.response_media_type != "application/json":
            return "{ value, _, _ in try apiDecodeString(value) }"
        if self.response_payload_proto is None:
            return "{ _, _, _ in () }"
        return (
            "{ data, envelope, coding in try apiDecodeResponse("
            + self.response_type.text
            + ".self, from: data, envelope: envelope, routeID: "
            + json.dumps(self.protocol.route.route_id)
            + ", coding: coding) }"
        )

    @property
    def query_to_items_expr(self) -> str:
        return "query?.toQueryItems() ?? []" if self.query_type else "[]"

    @property
    def path_to_items_expr(self) -> str:
        return "path.toQueryItems()" if self.path_type else "[]"

    @property
    def open_to_query_expr(self) -> str:
        return "open?.toQueryItems() ?? []" if self.open_type else self.query_to_items_expr

    @property
    def connection_query_expr(self) -> str:
        if self.query_type and self.open_type:
            return "(query?.toQueryItems() ?? []) + (openPayload?.toQueryItems() ?? [])"
        if self.open_type:
            return "openPayload?.toQueryItems() ?? []"
        if self.query_type:
            return "query?.toQueryItems() ?? []"
        return "[]"

    def message_helpers(self) -> tuple[SwiftMessageHelper, ...]:
        return self._message_helpers

    def _ensure_model(self, model: Optional[Union[Type[Model], Model]], suffix: str) -> Optional[SwiftProto]:
        if model is None:
            return None
        auto_flag = getattr(model, "__auto__", False)
        is_route_model = auto_flag or isinstance(model, FieldWrappedModel)
        if auto_flag:
            name = f"{self.group_class.removesuffix('API')}{self.func_name}{suffix}"
        else:
            name = getattr(model, "__name__", None) or f"{self.func_name}{suffix}"
        tag = "route" if is_route_model else "shared"
        module = self.group_slug if is_route_model else "shared"
        return self.registry.ensure(model, name=name, tag=tag, module=module)

    def _ensure_message_contract(self, contract: MessageContract | None, suffix: str) -> SwiftProto | SwiftMessageRef | None:
        if contract is None:
            return None
        if contract.single_model is not None:
            return self._ensure_model(contract.single_model, suffix)
        for variant in contract.variants:
            self._ensure_model(variant.model, f"{suffix}{variant.key.capitalize()}")
        if contract.name:
            return SwiftMessageRef(contract.name)  # type: ignore[return-value]
        return self.registry.register_alias(
            contract.name or f"{self.group_class.removesuffix('API')}{self.func_name}{suffix}",
            SwiftResolvedType("APIJSONValue"),
            tag="route",
            module=self.group_slug,
        )

    def _payload_response_type(self) -> SwiftResolvedType:
        if self.response_kind in {"bytes", "file"}:
            return SwiftResolvedType("APIRawResponse")
        if self.response_kind == "byte_stream":
            return SwiftResolvedType("APIStreamResponse")
        if self.response_kind == "binary_schema" and self.response_binary_schema_obj is not None:
            return SwiftResolvedType(self.response_binary_schema_obj.name)
        if self.response_media_type != "application/json":
            return SwiftResolvedType("String")
        if self.response_payload_proto is None:
            return SwiftResolvedType("Void")
        return SwiftResolvedType(self.response_payload_proto.name, {self.response_payload_proto})

    def _build_message_helpers(self) -> tuple[SwiftMessageHelper, ...]:
        helpers: list[SwiftMessageHelper] = []
        for contract, suffix in (
            (self.protocol.server_message, "ServerMessage"),
            (self.protocol.client_message, "ClientMessage"),
        ):
            if contract is None or not contract.is_union or contract.name is None or not contract.variants:
                continue
            variants: list[SwiftMessageVariant] = []
            for variant in contract.variants:
                proto = self._ensure_model(variant.model, f"{suffix}{variant.key.capitalize()}")
                if proto is None:
                    continue
                variants.append(
                    SwiftMessageVariant(
                        key=variant.key,
                        case_name=to_swift_identifier(variant.key),
                        static_name=to_swift_identifier(variant.key),
                        data_type=proto.name,
                    )
                )
            if variants:
                helpers.append(SwiftMessageHelper(name=contract.name, variants=tuple(variants)))
        return tuple(helpers)


@dataclass
class SwiftApiGroup:
    slug: str
    class_name: str
    property_name: str
    path: str
    type_stem: str
    routes: list[SwiftRoute] = field(default_factory=list)

    def binary_schemas(self) -> list[SwiftBinarySchema]:
        return unique_swift_binary_schemas(
            [
                schema
                for route in self.routes
                for schema in (route.binary_schema, route.response_binary_schema)
                if schema is not None
            ]
        )

    def message_helpers(self) -> tuple[SwiftMessageHelper, ...]:
        helpers: "OrderedDict[str, SwiftMessageHelper]" = OrderedDict()
        for route in self.routes:
            for helper in route.message_helpers():
                helpers.setdefault(helper.name, helper)
        return tuple(helpers.values())


class SwiftBlueprint(BaseBlueprint["SwiftWriter"]):
    def __init__(self, writer: "SwiftWriter", bp):
        super().__init__(writer, bp)
        self.registry = SwiftProtoRegistry()
        self.routes: list[SwiftRoute] = []
        self.groups: "OrderedDict[str, SwiftApiGroup]" = OrderedDict()

    @property
    def root_path(self) -> str:
        return to_swift_path(self.bp.root_slug, fallback="API")

    @property
    def root_type(self) -> str:
        return to_swift_type_name(self.bp.root_slug, fallback="API")

    @property
    def root_client(self) -> str:
        return f"{self.root_type}RootClient"

    @property
    def gen_root_client(self) -> str:
        return f"Gen{self.root_client}"

    @property
    def root_property(self) -> str:
        return to_swift_identifier(self.bp.root_slug, fallback="api")

    def collect(self) -> None:
        self.routes = []
        self.groups = OrderedDict()
        for _group, router in self.iter_router():
            protocol = self.protocol_for_router(router)
            route_name = protocol.route.func_name
            if not self.writer.includes(router, route_name=route_name):
                continue
            self._register_common_models(protocol)
            route = SwiftRoute(router, self.registry, protocol=protocol)
            self.routes.append(route)
            group = self.groups.get(route.group_slug)
            if group is None:
                group_path = self._route_group_path(route.group_slug)
                type_stem = to_swift_type_name(route.group_slug.rsplit("/", 1)[-1], fallback="Root")
                group = SwiftApiGroup(
                    slug=route.group_slug,
                    class_name=f"{type_stem}API",
                    property_name=to_swift_identifier(route.group_slug),
                    path=to_swift_path(group_path, fallback="API"),
                    type_stem=type_stem,
                )
                self.groups[route.group_slug] = group
            group.routes.append(route)

    def protocol_for_router(self, router: Router) -> RouteProtocolContract:
        return self.writer.route_protocol_for(router)

    def _route_group_path(self, group_slug: str) -> str:
        root = self.bp.root_slug
        group_path = group_slug.strip("/")
        if not root:
            return group_path
        if group_path == root or group_path.startswith(f"{root}/"):
            return group_path
        return f"{root}/{group_path}"

    def _register_common_models(self, protocol: RouteProtocolContract) -> None:
        def collect(model: Optional[Union[Type[Model], Model]]) -> None:
            if model is None:
                return
            model_cls = unwrap_model_type(model)
            origin = get_origin(model_cls)
            if origin is not None:
                try:
                    if issubclass(origin, Model):
                        model_cls = origin
                except TypeError:
                    pass
            for nested in iter_field_model_type(model):
                if nested is model_cls or nested is FieldWrappedModel:
                    continue
                if getattr(nested, "__auto__", False):
                    continue
                self.registry.ensure(nested, tag="shared")
            if not getattr(model, "__auto__", False) and getattr(model_cls, "__auto__", False) is False:
                self.registry.ensure(model_cls, tag="shared")

        collect(protocol.request.query.model)
        collect(protocol.request.open.model)
        collect(protocol.request.form.model)
        collect(protocol.request.multipart.model)
        collect(protocol.request.json.model)
        collect(protocol.request.binary.model)
        collect(protocol.response.model.model)
        collect(protocol.close_model)
        if protocol.server_message:
            for variant in protocol.server_message.variants:
                collect(variant.model)
            collect(protocol.server_message.single_model)
        if protocol.client_message:
            for variant in protocol.client_message.variants:
                collect(variant.model)
            collect(protocol.client_message.single_model)
