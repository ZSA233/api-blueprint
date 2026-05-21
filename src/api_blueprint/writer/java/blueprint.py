from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Mapping

from api_blueprint.writer.core.base import BaseBlueprint
from api_blueprint.writer.core.message_helpers import unique_named_message_helpers
from api_blueprint.writer.core.sdk_names import RoutePublicNames

from .binary_schema import JavaBinarySchema, unique_java_binary_schemas
from .naming import to_java_member_name, to_java_package_path, to_java_package_suffix, to_java_type_name


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class JavaRouteParam:
    name: str
    java_type: str
    required: bool = True


@dataclass(frozen=True)
class JavaMessageVariant:
    key: str
    method_name: str
    data_type: str
    data_class: str


@dataclass(frozen=True)
class JavaMessageHelper:
    name: str
    variants_class: str
    handlers_interface: str
    exception_class: str
    dispatch_method: str
    variants: tuple[JavaMessageVariant, ...]


class JavaRoute:
    def __init__(self, route: Mapping[str, Any]):
        self.route = dict(route)
        self.route_id = str(route.get("id") or "")
        self.kind = str(route.get("kind") or "rpc")
        self.operation = str(route.get("operation") or "Call")
        self.method_name = to_java_member_name(str(route.get("method_name") or self.operation), fallback="call")
        self.url = str(route.get("url") or "")
        raw_methods = route.get("methods")
        self.methods = tuple(str(method).upper() for method in raw_methods) if isinstance(raw_methods, list) else ("GET",)
        self.request = _mapping(route.get("request"))
        self.response = _mapping(route.get("response"))
        self.connection = _mapping(route.get("connection"))
        self.binary_schema = _mapping(self.request.get("binary_schema")) or None
        self.response_binary_schema = _mapping(self.response.get("binary_schema")) or None
        self.public_names = RoutePublicNames.from_operation(self.operation, fallback="Call")

    @property
    def operation_type_name(self) -> str:
        return self.public_names.operation

    @property
    def is_rpc(self) -> bool:
        return self.kind == "rpc"

    @property
    def http_method(self) -> str:
        return self.methods[0] if self.methods else "GET"

    @property
    def response_envelope_literal(self) -> str:
        envelope = _mapping(self.response.get("envelope"))
        fields = _mapping(envelope.get("fields"))
        return (
            "GenApiResponseEnvelope.of("
            f"{_java_string(envelope.get('name') or 'NoEnvelope')}, "
            f"{_java_string(envelope.get('kind') or 'none')}, "
            f"{_java_string(envelope.get('error_identity') or 'none')}, "
            f"{int(envelope.get('success_code') or 0)}, "
            f"{_java_string(envelope.get('success_message') or 'ok')}, "
            "new GenApiResponseEnvelope.Fields("
            f"{_java_string(fields.get('code') or 'code')}, "
            f"{_java_string(fields.get('message') or 'message')}, "
            f"{_java_string(fields.get('data') or 'data')}, "
            f"{_java_string(fields.get('error') or 'error')}, "
            f"{_java_string(fields.get('ok') or 'ok')}"
            ")"
            ")"
        )

    @property
    def response_model(self) -> str | None:
        value = self.response.get("model")
        return value if isinstance(value, str) and value else None

    @property
    def response_media_type(self) -> str:
        return str(self.response.get("media_type") or "application/json")

    @property
    def query_model(self) -> str | None:
        return _model_name(self.request.get("query_model"))

    @property
    def json_model(self) -> str | None:
        return _model_name(self.request.get("json_model"))

    @property
    def form_model(self) -> str | None:
        return _model_name(self.request.get("form_model"))

    @property
    def multipart_model(self) -> str | None:
        return _model_name(self.request.get("multipart_model"))

    @property
    def request_body_kind(self) -> str:
        return str(self.request.get("body_kind") or "none")

    @property
    def binary_model(self) -> str | None:
        if self.binary_schema is not None:
            return None
        return _model_name(self.request.get("binary_model"))

    @property
    def binary_schema_type(self) -> str | None:
        if self.binary_schema is None:
            return None
        return JavaBinarySchema(self.binary_schema).name

    @property
    def response_kind(self) -> str:
        return str(self.response.get("kind") or "json")

    @property
    def is_raw_response(self) -> bool:
        return self.response_kind in {"bytes", "file", "byte_stream"}

    @property
    def is_binary_schema_response(self) -> bool:
        return self.response_kind == "binary_schema" and self.response_binary_schema is not None

    @property
    def response_binary_schema_type(self) -> str | None:
        if self.response_binary_schema is None:
            return None
        return JavaBinarySchema(self.response_binary_schema).name

    @property
    def response_filename(self) -> str | None:
        value = self.response.get("default_filename") or self.response.get("filename")
        return str(value) if isinstance(value, str) and value else None

    @property
    def open_model(self) -> str | None:
        return _model_name(self.connection.get("open_model"))

    @property
    def close_model(self) -> str | None:
        return _model_name(self.connection.get("close_model"))

    @property
    def connection_method_name(self) -> str:
        if self.kind == "stream":
            return to_java_member_name(f"subscribe {self.operation}", fallback="subscribe")
        if self.kind == "channel":
            return to_java_member_name(f"open {self.operation}", fallback="open")
        return self.method_name

    @property
    def server_message_name(self) -> str | None:
        return _message_name(self.connection.get("server_message"))

    @property
    def client_message_name(self) -> str | None:
        return _message_name(self.connection.get("client_message"))

    def model_names(self) -> set[str]:
        names = {
            name
            for name in (
                self.query_model,
                self.json_model,
                self.form_model,
                self.multipart_model,
                self.binary_model,
                self.open_model,
                self.close_model,
                self.response_model,
            )
            if name
        }
        for message_key in ("server_message", "client_message"):
            message = self.connection.get(message_key)
            if isinstance(message, Mapping):
                single = _model_name(message.get("model"))
                if single:
                    names.add(single)
                variants = message.get("variants")
                if isinstance(variants, list):
                    for variant in variants:
                        if isinstance(variant, Mapping):
                            model = _model_name(variant.get("model"))
                            if model:
                                names.add(model)
        return names


@dataclass
class JavaApiGroup:
    root: str
    group: str
    route_path: str
    package_path: str
    package_suffix: str
    class_name: str
    service_class: str
    types_class: str
    runtime_types_ref: str
    property_name: str
    routes: list[JavaRoute] = field(default_factory=list)
    schema_type_names: dict[str, str] = field(default_factory=dict)

    @property
    def controller_class(self) -> str:
        return f"Gen{self.class_name.removesuffix('Api')}Controller"

    @property
    def generated_client_class(self) -> str:
        return f"Gen{self.class_name}"

    @property
    def generated_service_class(self) -> str:
        return f"Gen{self.service_class}"

    @property
    def stub_class(self) -> str:
        return f"Gen{self.service_class}Stub"

    def schema_type_name(self, schema_name: str) -> str:
        return self.schema_type_names.get(schema_name, to_java_type_name(schema_name.rsplit(".", 1)[-1], fallback="Model"))

    def register_route_model_names(self, route: JavaRoute, *, is_auto_schema) -> None:
        slots = (
            (route.query_model, route.public_names.query),
            (route.json_model, route.public_names.json),
            (route.form_model, route.public_names.form),
            (route.multipart_model, route.public_names.form),
            (route.binary_model, route.public_names.binary),
            (route.open_model, route.public_names.open),
            (route.close_model, route.public_names.close),
            (route.response_model, route.public_names.response),
        )
        for schema_name, type_name in slots:
            if schema_name and is_auto_schema(schema_name):
                self.schema_type_names.setdefault(schema_name, type_name)

    def model_names(self) -> set[str]:
        names: set[str] = set()
        for route in self.routes:
            names.update(route.model_names())
        return names

    def binary_schemas(self) -> tuple[JavaBinarySchema, ...]:
        return unique_java_binary_schemas(
            [
                schema
                for route in self.routes
                for schema in (route.binary_schema, route.response_binary_schema)
                if schema is not None
            ]
        )

    def message_helpers(self, writer: "JavaBaseWriter") -> tuple[JavaMessageHelper, ...]:
        helpers: list[JavaMessageHelper] = []
        for descriptor in unique_named_message_helpers([route.route for route in self.routes]):
            variants = tuple(
                JavaMessageVariant(
                    key=variant.key,
                    method_name=to_java_member_name(variant.key, fallback="variant"),
                    data_type=writer.schema_type(variant.model, self),
                    data_class=writer.schema_class_literal(variant.model, self),
                )
                for variant in descriptor.variants
            )
            helpers.append(
                JavaMessageHelper(
                    name=descriptor.name,
                    variants_class=f"{descriptor.name}Variants",
                    handlers_interface=f"{descriptor.name}Handlers",
                    exception_class=f"{descriptor.name}DispatchException",
                    dispatch_method=to_java_member_name(f"dispatch {descriptor.name}", fallback="dispatchMessage"),
                    variants=variants,
                )
            )
        return tuple(helpers)


class JavaBlueprint(BaseBlueprint["JavaBaseWriter"]):
    def __init__(self, writer: "JavaBaseWriter", bp: Any):
        super().__init__(writer, bp)
        self.routes: list[JavaRoute] = []
        self.groups: "OrderedDict[str, JavaApiGroup]" = OrderedDict()

    @property
    def root_slug(self) -> str:
        return self.bp.root.strip("/") or "root"

    @property
    def root_package_path(self) -> str:
        return to_java_package_path(self.root_slug, fallback="api")

    @property
    def root_package_suffix(self) -> str:
        return to_java_package_suffix(self.root_slug, fallback="api")

    @property
    def root_package(self) -> str:
        return f"{self.writer.package}.{self.root_package_suffix}"

    def collect_from_manifest(self, routes: list[Mapping[str, Any]], services: Mapping[str, Mapping[str, Any]]) -> None:
        self.routes = []
        self.groups = OrderedDict()
        for route_manifest in routes:
            route = JavaRoute(route_manifest)
            root, group = _route_root_group(route_manifest, services)
            if root != self.root_slug:
                continue
            self.routes.append(route)
            group_obj = self.groups.get(group)
            if group_obj is None:
                route_path = root if group == root else f"{root}/{group}"
                package_path = to_java_package_path(route_path, fallback="api")
                package_suffix = to_java_package_suffix(route_path, fallback="api")
                base_name = to_java_type_name(group, fallback="Root")
                group_obj = JavaApiGroup(
                    root=root,
                    group=group,
                    route_path=route_path,
                    package_path=package_path,
                    package_suffix=package_suffix,
                    class_name=f"{base_name}Api",
                    service_class=f"{base_name}Service",
                    types_class=f"Gen{base_name}Types",
                    runtime_types_ref=(
                        f"{self.root_package}.runtime.GenApiTypes" if base_name == "Api" else "GenApiTypes"
                    ),
                    property_name=to_java_member_name(group, fallback="api"),
                )
                self.groups[group] = group_obj
            group_obj.routes.append(route)
            group_obj.register_route_model_names(route, is_auto_schema=self.writer.catalog.is_auto_schema)


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _model_name(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _message_name(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    return _model_name(value.get("name"))


def _java_string(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _route_root_group(
    route: Mapping[str, Any],
    services: Mapping[str, Mapping[str, Any]],
) -> tuple[str, str]:
    service = services.get(str(route.get("service_id") or ""), {})
    root = str(service.get("root") or _service_root(route) or "api").strip("/") or "api"
    group = str(service.get("group") or root).strip("/") or root
    return root, group


def _service_root(route: Mapping[str, Any]) -> str:
    service_id = str(route.get("service_id") or "api")
    return service_id.split(".", 1)[0]


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .writer import JavaBaseWriter
