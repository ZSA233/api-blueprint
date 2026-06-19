from __future__ import annotations

import json
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping

from api_blueprint.engine.model import Model
from api_blueprint.engine.router import Router
from api_blueprint.writer.core.base import BaseBlueprint
from api_blueprint.writer.core.contract_adapters import RouteProtocolContract
from api_blueprint.writer.core.message_helpers import MessageHelperDescriptor
from api_blueprint.writer.core.sdk_names import RoutePublicNames

from .naming import to_path_segments, to_py_class_name, to_py_identifier
from .binary_schema import PythonBinarySchema, unique_python_binary_schemas
from .schema_types import PythonDtoModel, PythonEnumModel, PythonResolvedType, PythonSchemaRegistry

if TYPE_CHECKING:
    from .writer import PythonBaseWriter


@dataclass(frozen=True)
class PythonRequestParam:
    name: str
    call_name: str
    annotation: str = "Any | None"
    server_annotation: str | None = None
    default: str | None = None
    type: PythonResolvedType | None = None
    transport_encode: bool = False

    @property
    def service_annotation(self) -> str:
        return self.server_annotation or self.annotation

    def encode_expr(self, value_expr: str) -> str:
        if self.transport_encode:
            return f"_api_to_transport({value_expr})"
        if self.type is None:
            return value_expr
        return f"_api_to_json({value_expr})"

    def decode_expr(self, value_expr: str, path_expr: str) -> str:
        if self.type is None:
            return value_expr
        return self.type.decode_expr(value_expr, path_expr)


@dataclass(frozen=True)
class PythonMessageVariant:
    key: str
    method_name: str
    data_type: str
    data_decode_expr: str
    case_data_decode_expr: str
    case_class: str
    handler_name: str


@dataclass(frozen=True)
class PythonMessageHelper:
    name: str
    variants_class: str
    handlers_class: str
    processor_class: str
    case_interface: str
    error_class: str
    dispatch_func: str
    visit_func: str
    is_error_func: str
    variants: tuple[PythonMessageVariant, ...]


class PythonRoute:
    def __init__(self, router: Router, protocol: RouteProtocolContract, *, registry: PythonSchemaRegistry):
        self.router = router
        self.protocol = protocol
        self.contract = protocol.route
        self.method_name = to_py_identifier(self.contract.method_name, default="call")
        self.public_names = RoutePublicNames.from_operation(self.contract.func_name, fallback="Call")
        self.operation_class = self.public_names.operation
        self.url = self.contract.url
        self.http_methods = tuple(self.contract.http_methods or ("GET",))
        self.response_type = _model_name(protocol.response.model.model)
        self.response_schema = protocol.response.model.schema
        self.response_envelope = protocol.response.envelope.envelope_spec()
        self.binary_schema = protocol.request.binary_schema
        self.response_binary_schema = protocol.response.binary_schema
        self.registry = registry
        self.query_type = registry.resolve_schema(protocol.request.query.schema, class_name=self.public_names.query)
        self.json_type = registry.resolve_schema(protocol.request.json.schema, class_name=self.public_names.json)
        self.form_type = registry.resolve_schema(protocol.request.form.schema, class_name=self.public_names.form)
        self.multipart_type = registry.resolve_schema(protocol.request.multipart.schema, class_name=self.public_names.form)
        self.open_type = registry.resolve_schema(protocol.request.open.schema, class_name=self.public_names.open)
        self.response_type_info = registry.resolve_schema(
            protocol.response.model.schema,
            class_name=self.public_names.response,
        )
        self.server_message_type = self._ensure_message_contract(protocol.server_message)
        self.client_message_type = self._ensure_message_contract(protocol.client_message)
        self.close_type = self._ensure_model_ref(protocol.close_model, self.public_names.close)
        self.params = self._request_params()

    @property
    def is_rpc(self) -> bool:
        return not (self.supports_stream or self.supports_channel)

    @property
    def supports_stream(self) -> bool:
        return self.contract.supports_stream

    @property
    def supports_channel(self) -> bool:
        return self.contract.supports_channel

    @property
    def subscribe_method_name(self) -> str:
        method = self.contract.stream.connect_method if self.contract.stream is not None else f"subscribe_{self.method_name}"
        return to_py_identifier(method, default=f"subscribe_{self.method_name}")

    @property
    def open_channel_method_name(self) -> str:
        method = self.contract.channel.connect_method if self.contract.channel is not None else f"open_{self.method_name}"
        return to_py_identifier(method, default=f"open_{self.method_name}")

    @property
    def connection_kind_literal(self) -> str:
        if self.supports_stream:
            return json.dumps("stream")
        if self.supports_channel:
            return json.dumps("channel")
        return json.dumps("rpc")

    @property
    def route_id_literal(self) -> str:
        return json.dumps(self.contract.route_id)

    @property
    def http_route_info_name(self) -> str:
        source = self.contract.route_id or self.method_name
        tokens = [token for token in re.split(r"[^0-9A-Za-z]+", source) if token]
        name = "_".join(token.upper() for token in tokens) or "ROUTE"
        if name[:1].isdigit():
            name = f"ROUTE_{name}"
        return f"_HTTP_ROUTE_{name}"

    @property
    def response_envelope_literal(self) -> str:
        return json.dumps(self.response_envelope, ensure_ascii=False)

    @property
    def websocket_endpoint_name(self) -> str:
        return f"{self.open_channel_method_name}_socket"

    @property
    def channel_scaffold(self) -> dict[str, str] | None:
        if not self.supports_channel:
            return None
        descriptor = _descriptor_from_contract(self.protocol.server_message)
        if descriptor is None:
            return None
        message_name = descriptor.name
        return {
            "session_class": f"{self.operation_class}ChannelSession",
            "message_type": message_name,
            "send_type": self.client_message_type.annotation if self.client_message_type is not None else "Any",
            "processor_type": f"{message_name}Processor",
            "visit_func": f"visit_{to_py_identifier(message_name, default='message')}",
            "close_type": self.close_type.annotation if self.close_type is not None else "Any",
        }

    @property
    def response_type_literal(self) -> str:
        if self.is_binary_schema_response:
            return repr("binary_schema")
        if self.is_raw_response:
            return repr(self.raw_response_transport_type)
        if self.response_type_info is not None:
            return repr(self.response_type_info.annotation)
        if self.response_type is None:
            return "None"
        return repr(self.response_type)

    @property
    def response_class_name(self) -> str | None:
        if self.response_type_info is None:
            return None
        return self.response_type_info.annotation

    @property
    def response_annotation(self) -> str:
        if self.is_binary_schema_response:
            return self.response_binary_schema.name
        if self.protocol.response.kind in {"bytes", "file"}:
            return "ApiRawResponse[bytes]"
        if self.protocol.response.kind == "byte_stream":
            return "ApiStreamResponse"
        if self.response_type_info is None:
            return "Any"
        return self.response_type_info.annotation

    @property
    def service_response_annotation(self) -> str:
        if self.is_binary_schema_response:
            return self.response_binary_schema.name
        if self.protocol.response.kind == "bytes":
            return "bytes | ApiRawResponse[bytes]"
        if self.protocol.response.kind == "file":
            return "str | Path | ApiRawResponse[bytes]"
        if self.protocol.response.kind == "byte_stream":
            return "AsyncIterable[bytes] | Iterable[bytes] | ApiRawResponse[AsyncIterable[bytes] | Iterable[bytes]]"
        return self.response_annotation

    @property
    def is_raw_response(self) -> bool:
        return self.protocol.response.kind in {"bytes", "file", "byte_stream"}

    @property
    def is_binary_schema_response(self) -> bool:
        return self.protocol.response.kind == "binary_schema" and self.response_binary_schema is not None

    @property
    def raw_response_transport_type(self) -> str:
        if self.protocol.response.kind == "byte_stream":
            return "stream"
        return self.protocol.response.kind

    @property
    def response_kind_literal(self) -> str:
        return json.dumps(self.protocol.response.kind)

    @property
    def response_media_type_literal(self) -> str:
        return json.dumps(self.protocol.response.media_type)

    @property
    def response_filename_literal(self) -> str:
        if self.protocol.response.filename is None:
            return "None"
        return repr(self.protocol.response.filename)

    def response_decode_expr(self, value_expr: str) -> str:
        if self.is_binary_schema_response:
            return f"{self.response_binary_wire_name}.from_bytes({value_expr})"
        if self.is_raw_response:
            return value_expr
        if self.response_type_info is None:
            return value_expr
        if self.is_enveloped_empty_object_response:
            return (
                f"{self.response_type_info.annotation}.from_empty_response_value("
                f"{value_expr}, {json.dumps(f'{self.method_name}.response')})"
            )
        return self.response_type_info.decode_expr(value_expr, json.dumps(f"{self.method_name}.response"))

    @property
    def has_binary_schema(self) -> bool:
        return self.binary_schema is not None

    @property
    def has_response_binary_schema(self) -> bool:
        return self.response_binary_schema is not None

    @property
    def is_enveloped_empty_object_response(self) -> bool:
        if self.response_envelope.get("kind") == "none":
            return False
        return _is_empty_object_schema(self.response_schema, self.registry.schemas)

    @property
    def binary_type_name(self) -> str | None:
        if self.binary_schema is None:
            return None
        return self.binary_schema.name

    @property
    def binary_wire_name(self) -> str | None:
        if self.binary_schema is None:
            return None
        return f"{self.binary_schema.name}Wire"

    @property
    def binary_content_encodings_literal(self) -> str:
        if self.binary_schema is None:
            return repr(("identity",))
        return repr(tuple(self.binary_schema.content_encoding or ("identity",)))

    @property
    def response_binary_wire_name(self) -> str | None:
        if self.response_binary_schema is None:
            return None
        return f"{self.response_binary_schema.name}Wire"

    @property
    def http_method_literal(self) -> str:
        return json.dumps(self.http_methods[0])

    @property
    def url_literal(self) -> str:
        return json.dumps(self.url)

    @property
    def method_list_literal(self) -> str:
        return json.dumps(list(self.http_methods))

    @property
    def method_name_literal(self) -> str:
        return json.dumps(self.method_name)

    @property
    def client_call_args(self) -> str:
        if not self.params:
            return ""
        return ", ".join(f"{param.call_name}={param.name}" for param in self.params)

    @property
    def has_decoded_params(self) -> bool:
        return self.has_binary_schema or any(param.type is not None for param in self.params)

    def _request_params(self) -> list[PythonRequestParam]:
        params: list[PythonRequestParam] = []
        if self.protocol.request.query.model is not None:
            params.append(_request_param("query", "query", self.query_type))
        if self.protocol.request.json.model is not None:
            params.append(_request_param("json", "json", self.json_type))
        if self.protocol.request.form.model is not None:
            params.append(_request_param("form", "form", self.form_type))
        if self.protocol.request.multipart.model is not None:
            params.append(_request_param("multipart", "multipart", self.multipart_type, transport_encode=True))
        if self.binary_schema is not None:
            params.append(
                PythonRequestParam(
                    "binary",
                    "binary",
                    f"{self.binary_schema.name} | ApiBinaryBody",
                    self.binary_schema.name,
                    None,
                    type=None,
                )
            )
        elif self.protocol.request.binary.model is not None:
            params.append(PythonRequestParam("binary", "binary", "bytes | None", "bytes | None", None, type=None))
        if self.protocol.request.open.model is not None:
            params.append(_request_param("open_data", "open_data", self.open_type))
        return params

    def message_helpers(self) -> tuple[PythonMessageHelper, ...]:
        helpers: list[PythonMessageHelper] = []
        for contract in (self.protocol.server_message, self.protocol.client_message):
            descriptor = _descriptor_from_contract(contract)
            if descriptor is None:
                continue
            variants: list[PythonMessageVariant] = []
            for variant in descriptor.variants:
                data_type = self.registry.resolve_schema(variant.model, class_name=_message_payload_type(variant.model))
                resolved = data_type or PythonResolvedType("Any")
                variants.append(
                    PythonMessageVariant(
                        key=variant.key,
                        method_name=to_py_identifier(variant.key, default="variant"),
                        data_type=resolved.annotation,
                        data_decode_expr=resolved.decode_expr(
                            "typed_message.data",
                            f"_field_path({json.dumps(descriptor.name)}, \"data\")",
                        ),
                        case_data_decode_expr=resolved.decode_expr(
                            "self._message.data",
                            f"_field_path({json.dumps(descriptor.name)}, \"data\")",
                        ),
                        case_class=f"{descriptor.name}{to_py_class_name(variant.key, default='Variant')}Case",
                        handler_name=f"on_{to_py_identifier(variant.key, default='variant')}",
                    )
                )
            helpers.append(
                PythonMessageHelper(
                    name=descriptor.name,
                    variants_class=f"{descriptor.name}Variants",
                    handlers_class=f"{descriptor.name}Handlers",
                    processor_class=f"{descriptor.name}Processor",
                    case_interface=f"{descriptor.name}Case",
                    error_class=f"{descriptor.name}DispatchError",
                    dispatch_func=f"dispatch_{to_py_identifier(descriptor.name, default='message')}",
                    visit_func=f"visit_{to_py_identifier(descriptor.name, default='message')}",
                    is_error_func=f"is_{to_py_identifier(descriptor.name, default='message')}_dispatch_error",
                    variants=tuple(variants),
                )
            )
        return tuple(helpers)

    def _ensure_model_ref(self, model: object, class_name: str | None = None) -> PythonResolvedType:
        schema_name = _model_name(model)
        resolved = self.registry.resolve_schema(schema_name, class_name=class_name)
        return resolved or PythonResolvedType("Any")

    def _ensure_message_contract(self, contract: object) -> PythonResolvedType | None:
        descriptor = _descriptor_from_contract(contract)
        if descriptor is None:
            single_model = getattr(contract, "single_model", None)
            if single_model is None:
                return None
            return self._ensure_model_ref(single_model)
        for variant in descriptor.variants:
            self.registry.resolve_schema(variant.model, class_name=_message_payload_type(variant.model))
        return PythonResolvedType(descriptor.name, f"{descriptor.name}.from_value")


@dataclass
class PythonRouteGroup:
    alias: str
    segments: tuple[str, ...]
    legacy_segments: tuple[str, ...]
    client_class: str
    service_class: str
    registry: PythonSchemaRegistry
    routes: list[PythonRoute] = field(default_factory=list)

    @property
    def package_path(self) -> str:
        return ".".join(self.segments)

    @property
    def runtime_import_prefix(self) -> str:
        return "." * (len(self.segments) + 2)

    def binary_schemas(self) -> list[PythonBinarySchema]:
        schemas = []
        for route in self.routes:
            if route.binary_schema is not None:
                schemas.append(route.binary_schema)
            if route.response_binary_schema is not None:
                schemas.append(route.response_binary_schema)
        return unique_python_binary_schemas(schemas)

    def route_models(self) -> tuple[PythonDtoModel, ...]:
        return self.registry.models()

    def enums(self) -> tuple[PythonEnumModel, ...]:
        return self.registry.enums()

    def type_import_names(self) -> tuple[str, ...]:
        names = [model.class_name for model in self.route_models()]
        names.extend(enum.class_name for enum in self.enums())
        names.extend(helper.name for helper in self.message_helpers())
        return tuple(dict.fromkeys(names))

    @property
    def server_type_module_alias(self) -> str:
        return f"{to_py_identifier('_'.join(self.segments), default='types')}_types"

    def server_type_expr(self, expr: str) -> str:
        result = expr
        names = list(self.type_import_names())
        for schema in self.binary_schemas():
            names.append(schema.py_type)
            names.append(f"{schema.py_type}Wire")
        for name in sorted(dict.fromkeys(names), key=len, reverse=True):
            result = re.sub(
                rf"(?<![\w.]){re.escape(name)}(?=\.)",
                f"{self.server_type_module_alias}.{name}",
                result,
            )
        return result

    def message_helpers(self) -> tuple[PythonMessageHelper, ...]:
        helpers: "OrderedDict[str, PythonMessageHelper]" = OrderedDict()
        for route in self.routes:
            for helper in route.message_helpers():
                helpers.setdefault(helper.name, helper)
        return tuple(helpers.values())


class PythonBlueprint(BaseBlueprint["PythonBaseWriter"]):
    def __init__(self, writer: "PythonBaseWriter", bp: Any):
        super().__init__(writer, bp)
        self.routes: list[PythonRoute] = []
        self.groups: "OrderedDict[tuple[str, ...], PythonRouteGroup]" = OrderedDict()

    @property
    def root_segments(self) -> tuple[str, ...]:
        return to_path_segments(self.bp.root_slug, default="root")

    def collect(self) -> None:
        self.routes = []
        self.groups = OrderedDict()
        schemas = self.writer.manifest_schemas()
        for _group, router in self.iter_router():
            protocol = self.writer.route_protocol_for(router)
            if not self.writer.route_selected(router, protocol):
                continue
            segments = self._group_segments(router)
            group = self.groups.get(segments)
            if group is None:
                alias = protocol.route.group_alias or segments[-1]
                group = PythonRouteGroup(
                    alias=alias,
                    segments=segments,
                    legacy_segments=self._legacy_group_segments(router),
                    client_class=to_py_class_name(protocol.route.client_class, default="ApiClient"),
                    service_class=to_py_class_name(protocol.route.service_name, default="ApiService"),
                    registry=PythonSchemaRegistry(schemas),
                )
                self.groups[segments] = group
            route = PythonRoute(router, protocol, registry=group.registry)
            self.routes.append(route)
            group.routes.append(route)

    def _group_segments(self, router: Router) -> tuple[str, ...]:
        branch_segments = self._branch_segments(router)
        return (*self.root_segments, *branch_segments)

    def _legacy_group_segments(self, router: Router) -> tuple[str, ...]:
        branch_segments = self._branch_segments(router)
        if not branch_segments:
            return ("root",)
        return branch_segments

    def _branch_segments(self, router: Router) -> tuple[str, ...]:
        branch = router.group.branch.strip("/")
        if not branch:
            return ()
        return to_path_segments(branch, default="root")


def _model_name(model: type[Model] | Model | None) -> str | None:
    if model is None:
        return None
    name = getattr(model, "__name__", None)
    if isinstance(name, str) and name:
        return name
    cls_name = model.__class__.__name__
    return cls_name if cls_name != "FieldWrappedModel" else None


def _message_payload_type(schema_name: str) -> str:
    return to_py_class_name(schema_name.rsplit(".", 1)[-1], default="MessageData")


def _is_empty_object_schema(schema_name: str | None, schemas: Mapping[str, object]) -> bool:
    if not schema_name:
        return False
    schema = schemas.get(schema_name)
    if not isinstance(schema, Mapping):
        return False
    if schema.get("type") != "object":
        return False
    fields = schema.get("fields")
    return isinstance(fields, Mapping) and not fields


def _request_param(
    name: str,
    call_name: str,
    resolved: PythonResolvedType | None,
    *,
    transport_encode: bool = False,
) -> PythonRequestParam:
    if resolved is None:
        return PythonRequestParam(name, call_name, "Any", type=None, transport_encode=transport_encode)
    return PythonRequestParam(
        name,
        call_name,
        resolved.annotation,
        type=resolved,
        transport_encode=transport_encode,
    )


def _descriptor_from_contract(contract: object) -> MessageHelperDescriptor | None:
    from api_blueprint.engine.connection import MessageContract
    from api_blueprint.writer.core.message_helpers import MessageVariantDescriptor

    if not isinstance(contract, MessageContract):
        return None
    if not contract.is_union or contract.name is None or not contract.variants:
        return None
    return MessageHelperDescriptor(
        name=contract.name,
        direction="server",
        variants=tuple(
            MessageVariantDescriptor(
                key=variant.key,
                model=_model_name(variant.model) or variant.key,
            )
            for variant in contract.variants
        ),
    )
