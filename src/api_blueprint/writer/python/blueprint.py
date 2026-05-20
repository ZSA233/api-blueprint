from __future__ import annotations

import json
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

if TYPE_CHECKING:
    from .writer import PythonBaseWriter


@dataclass(frozen=True)
class PythonRequestParam:
    name: str
    call_name: str
    annotation: str = "dict[str, Any] | None"
    server_annotation: str | None = None
    default: str = "None"
    converter: str = "_to_mapping"

    @property
    def service_annotation(self) -> str:
        return self.server_annotation or "dict[str, Any] | None"


@dataclass(frozen=True)
class PythonRouteModelField:
    name: str
    type_expr: str


@dataclass(frozen=True)
class PythonRouteModel:
    class_name: str
    fields: tuple[PythonRouteModelField, ...]


@dataclass(frozen=True)
class PythonMessageVariant:
    key: str
    method_name: str
    data_type: str


@dataclass(frozen=True)
class PythonMessageHelper:
    name: str
    variants_class: str
    handlers_class: str
    error_class: str
    dispatch_func: str
    is_error_func: str
    variants: tuple[PythonMessageVariant, ...]


class PythonRoute:
    def __init__(self, router: Router, protocol: RouteProtocolContract, *, schemas: Mapping[str, Any]):
        self.router = router
        self.protocol = protocol
        self.contract = protocol.route
        self.method_name = to_py_identifier(self.contract.method_name, default="call")
        self.public_names = RoutePublicNames.from_operation(self.contract.func_name, fallback="Call")
        self.operation_class = self.public_names.operation
        self.url = self.contract.url
        self.http_methods = tuple(self.contract.http_methods or ("GET",))
        self.response_type = _model_name(protocol.response.model.model)
        self.response_envelope = protocol.response.envelope.envelope_spec()
        self.binary_schema = protocol.request.binary_schema
        self.query_model = _route_model(schemas, protocol.request.query.schema, self.public_names.query)
        self.json_model = _route_model(schemas, protocol.request.json.schema, self.public_names.json)
        self.form_model = _route_model(schemas, protocol.request.form.schema, self.public_names.form)
        self.open_model = _route_model(schemas, protocol.request.open.schema, self.public_names.open)
        self.response_model = _route_model(schemas, protocol.response.model.schema, self.public_names.response)
        self.message_payload_models = self._message_payload_models(schemas)
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
    def response_envelope_literal(self) -> str:
        return json.dumps(self.response_envelope, ensure_ascii=False)

    @property
    def websocket_endpoint_name(self) -> str:
        return f"{self.open_channel_method_name}_socket"

    @property
    def response_type_literal(self) -> str:
        if self.response_model is not None:
            return repr(self.response_model.class_name)
        if self.response_type is None:
            return "None"
        return repr(self.response_type)

    @property
    def response_class_name(self) -> str | None:
        return self.response_model.class_name if self.response_model is not None else None

    @property
    def has_binary_schema(self) -> bool:
        return self.binary_schema is not None

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

    def _request_params(self) -> list[PythonRequestParam]:
        params: list[PythonRequestParam] = []
        if self.protocol.request.query.model is not None:
            annotation = _param_annotation(self.query_model)
            params.append(PythonRequestParam("query", "query", annotation))
        if self.protocol.request.json.model is not None:
            annotation = _param_annotation(self.json_model)
            params.append(PythonRequestParam("json", "json", annotation))
        if self.protocol.request.form.model is not None:
            annotation = _param_annotation(self.form_model)
            params.append(PythonRequestParam("form", "form", annotation))
        if self.binary_schema is not None:
            params.append(
                PythonRequestParam(
                    "binary",
                    "binary",
                    f"{self.binary_schema.name} | ApiBinaryBody",
                    "bytes | None",
                    "...",
                    converter="",
                )
            )
        elif self.protocol.request.binary.model is not None:
            params.append(PythonRequestParam("binary", "binary", "bytes | None", "bytes | None", "None", converter=""))
        if self.protocol.request.open.model is not None:
            annotation = _param_annotation(self.open_model)
            params.append(PythonRequestParam("open_data", "open_data", annotation))
        return params

    def message_helpers(self) -> tuple[PythonMessageHelper, ...]:
        helpers: list[PythonMessageHelper] = []
        for contract in (self.protocol.server_message, self.protocol.client_message):
            descriptor = _descriptor_from_contract(contract)
            if descriptor is None:
                continue
            variants: list[PythonMessageVariant] = []
            for variant in descriptor.variants:
                variants.append(
                    PythonMessageVariant(
                        key=variant.key,
                        method_name=to_py_identifier(variant.key, default="variant"),
                        data_type=_message_payload_type(variant.model),
                    )
                )
            helpers.append(
                PythonMessageHelper(
                    name=descriptor.name,
                    variants_class=f"{descriptor.name}Variants",
                    handlers_class=f"{descriptor.name}Handlers",
                    error_class=f"{descriptor.name}DispatchError",
                    dispatch_func=f"dispatch_{to_py_identifier(descriptor.name, default='message')}",
                    is_error_func=f"is_{to_py_identifier(descriptor.name, default='message')}_dispatch_error",
                    variants=tuple(variants),
                )
            )
        return tuple(helpers)

    def _message_payload_models(self, schemas: Mapping[str, Any]) -> tuple[PythonRouteModel, ...]:
        models: list[PythonRouteModel] = []
        seen: set[str] = set()
        for contract in (self.protocol.server_message, self.protocol.client_message):
            descriptor = _descriptor_from_contract(contract)
            if descriptor is None:
                continue
            for variant in descriptor.variants:
                if variant.model in seen:
                    continue
                seen.add(variant.model)
                model = _route_model(schemas, variant.model, _message_payload_type(variant.model))
                if model is not None:
                    models.append(model)
        return tuple(models)


@dataclass
class PythonRouteGroup:
    alias: str
    segments: tuple[str, ...]
    legacy_segments: tuple[str, ...]
    client_class: str
    service_class: str
    routes: list[PythonRoute] = field(default_factory=list)

    @property
    def package_path(self) -> str:
        return ".".join(self.segments)

    @property
    def runtime_import_prefix(self) -> str:
        return "." * (len(self.segments) + 2)

    def binary_schemas(self) -> list[PythonBinarySchema]:
        schemas = [route.binary_schema for route in self.routes if route.binary_schema is not None]
        return unique_python_binary_schemas(schemas)

    def route_models(self) -> tuple[PythonRouteModel, ...]:
        result: list[PythonRouteModel] = []
        seen: set[str] = set()
        for route in self.routes:
            for model in (
                route.query_model,
                route.json_model,
                route.form_model,
                route.open_model,
                route.response_model,
                *route.message_payload_models,
            ):
                if model is None or model.class_name in seen:
                    continue
                seen.add(model.class_name)
                result.append(model)
        return tuple(result)

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
        return to_path_segments(self.bp.root, default="root")

    def collect(self) -> None:
        self.routes = []
        self.groups = OrderedDict()
        for _group, router in self.iter_router():
            protocol = self.writer.route_protocol_for(router)
            if not self.writer.route_selected(router, protocol):
                continue
            route = PythonRoute(router, protocol, schemas=self.writer.manifest_schemas())
            self.routes.append(route)
            segments = self._group_segments(router)
            group = self.groups.get(segments)
            if group is None:
                alias = route.contract.group_alias or segments[-1]
                group = PythonRouteGroup(
                    alias=alias,
                    segments=segments,
                    legacy_segments=self._legacy_group_segments(router),
                    client_class=to_py_class_name(route.contract.client_class, default="ApiClient"),
                    service_class=to_py_class_name(route.contract.service_name, default="ApiService"),
                )
                self.groups[segments] = group
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


def _route_model(schemas: Mapping[str, Any], schema_name: str | None, class_name: str) -> PythonRouteModel | None:
    if not schema_name:
        return None
    schema = schemas.get(schema_name)
    if not isinstance(schema, Mapping) or schema.get("type") != "object":
        return None
    fields = schema.get("fields")
    if not isinstance(fields, Mapping):
        return PythonRouteModel(class_name=class_name, fields=())
    rendered: list[PythonRouteModelField] = []
    for raw_name, raw_field in fields.items():
        if not isinstance(raw_field, Mapping):
            continue
        name = to_py_identifier(str(raw_field.get("name") or raw_name), default="value")
        rendered.append(PythonRouteModelField(name=name, type_expr=_python_type_for_value(raw_field)))
    return PythonRouteModel(class_name=class_name, fields=tuple(rendered))


def _param_annotation(model: PythonRouteModel | None) -> str:
    if model is None:
        return "Mapping[str, Any] | None"
    return f"{model.class_name} | Mapping[str, Any] | None"


def _python_type_for_value(value: Mapping[str, Any]) -> str:
    value_type = str(value.get("type") or "Any")
    if value.get("ref"):
        return "dict[str, Any]"
    if value_type == "array":
        return "list[Any]"
    if value_type == "map":
        return "dict[Any, Any]"
    return {
        "string": "str",
        "str": "str",
        "int": "int",
        "integer": "int",
        "int8": "int",
        "int16": "int",
        "int32": "int",
        "uint": "int",
        "uint8": "int",
        "uint16": "int",
        "uint32": "int",
        "int64": "int",
        "uint64": "int",
        "float": "float",
        "float32": "float",
        "float64": "float",
        "number": "float",
        "boolean": "bool",
        "bool": "bool",
        "binary": "bytes",
    }.get(value_type, "Any")
