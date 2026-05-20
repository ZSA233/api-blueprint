from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional, Type, Union, get_origin

from api_blueprint.engine.model import FieldWrappedModel, Model, iter_field_model_type, unwrap_model_type
from api_blueprint.engine.router import Router
from api_blueprint.writer.core.base import BaseBlueprint
from api_blueprint.engine.connection import MessageContract
from api_blueprint.writer.core.contract_adapters import RouteProtocolContract, route_protocol_from_router

from .binary_schema import KotlinBinarySchema, unique_kotlin_binary_schemas
from .naming import to_kotlin_package_path, to_kotlin_package_suffix, to_kotlin_property_name, to_kotlin_type_name
from .protos import KotlinProto, KotlinProtoRegistry, KotlinResolvedType
from .selection import KotlinRouteSelection


@dataclass(frozen=True)
class KotlinMessageRef:
    name: str


@dataclass(frozen=True)
class KotlinMessageVariant:
    key: str
    method_name: str
    data_type: str


@dataclass(frozen=True)
class KotlinMessageHelper:
    name: str
    variants_object: str
    handlers_interface: str
    dispatch_exception: str
    dispatch_func: str
    variants: tuple[KotlinMessageVariant, ...]


class KotlinRoute:
    def __init__(
        self,
        router: Router,
        registry: KotlinProtoRegistry,
        *,
        protocol: RouteProtocolContract | None = None,
    ):
        self.router = router
        self.registry = registry
        self.protocol = protocol or route_protocol_from_router(router)
        self.func_name = self.protocol.route.func_name
        self.method_name = to_kotlin_property_name(self.func_name)
        self.group_slug = self.protocol.route.group_slug
        self.group_class = to_kotlin_type_name(self.group_slug, fallback="Root") + "Api"
        self.url = self.protocol.route.url
        self.http_methods = list(self.protocol.route.http_methods)
        self.supports_stream = self.protocol.route.supports_stream
        self.supports_channel = self.protocol.route.supports_channel
        if self.is_rpc and len(self.http_methods) != 1:
            raise ValueError(f"[kotlin-client] Kotlin 客户端要求每个 route 只有一个 HTTP method: {self.url}")

        self.query_proto = self._ensure_model(self.protocol.request.query.model, "Query")
        self.open_proto = self._ensure_model(self.protocol.request.open.model, "Open")
        self.form_proto = self._ensure_model(self.protocol.request.form.model, "Form")
        self.json_proto = self._ensure_model(self.protocol.request.json.model, "Json")
        self.binary_schema = self.protocol.request.binary_schema
        self.binary_proto = None if self.binary_schema is not None else self._ensure_model(
            self.protocol.request.binary.model, "Binary"
        )

        self.response_media_type = self.protocol.response.media_type
        self.response_payload_proto = self._ensure_model(self.protocol.response.model.model, "Response")
        self.response_payload_type = self._payload_response_type()
        self.response_type = self.response_payload_type
        self.transport_response_type = self.response_payload_type
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
    def query_type(self) -> str | None:
        return self.query_proto.name if self.query_proto else None

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
    def binary_type(self) -> str | None:
        if self.binary_schema is not None:
            return self.binary_schema.name
        return self.binary_proto.name if self.binary_proto else None

    @property
    def binary_wire_type(self) -> str | None:
        if self.binary_schema is None:
            return None
        return f"{self.binary_schema.name}Wire"

    @property
    def has_binary_schema(self) -> bool:
        return self.binary_schema is not None

    @property
    def response_envelope_literal(self) -> str:
        spec = self.protocol.response.envelope.envelope_spec()
        fields = spec.get("fields") if isinstance(spec.get("fields"), dict) else {}
        return (
            "ApiResponseEnvelope("
            f"name = {_kotlin_string(spec.get('name') or 'NoEnvelope')}, "
            f"kind = {_kotlin_string(spec.get('kind') or 'none')}, "
            f"errorIdentity = {_kotlin_string(spec.get('error_identity') or 'none')}, "
            f"successCode = {int(spec.get('success_code') or 0)}, "
            f"successMessage = {_kotlin_string(spec.get('success_message') or 'ok')}, "
            "fields = ApiResponseEnvelopeFields("
            f"code = {_kotlin_string(fields.get('code') or 'code')}, "
            f"message = {_kotlin_string(fields.get('message') or 'message')}, "
            f"data = {_kotlin_string(fields.get('data') or 'data')}, "
            f"error = {_kotlin_string(fields.get('error') or 'error')}, "
            f"ok = {_kotlin_string(fields.get('ok') or 'ok')}"
            ")"
            ")"
        )

    @property
    def response_serializer_expr(self) -> str:
        return self.transport_response_type.serializer_expr()

    @property
    def server_message_type(self) -> str:
        return self.server_message_proto.name if self.server_message_proto else "kotlinx.serialization.json.JsonElement"

    @property
    def client_message_type(self) -> str:
        return self.client_message_proto.name if self.client_message_proto else "kotlinx.serialization.json.JsonElement"

    @property
    def close_type(self) -> str:
        return self.close_proto.name if self.close_proto else "SocketCloseInfo"

    @property
    def server_message_serializer_expr(self) -> str:
        return f"{self.server_message_type}.serializer()"

    @property
    def client_message_serializer_expr(self) -> str:
        return f"{self.client_message_type}.serializer()"

    @property
    def close_serializer_expr(self) -> str:
        return f"{self.close_type}.serializer()"

    @property
    def connection_query_expr(self) -> str:
        if self.query_type and self.open_type:
            return "query.toQueryMap() + open.toQueryMap()"
        if self.open_type:
            return "open.toQueryMap()"
        if self.query_type:
            return "query.toQueryMap()"
        return "emptyMap()"

    @property
    def subscribe_method_name(self) -> str:
        return to_kotlin_property_name(
            self.protocol.route.stream.connect_method if self.protocol.route.stream else f"subscribe{self.func_name}"
        )

    @property
    def open_channel_method_name(self) -> str:
        return to_kotlin_property_name(
            self.protocol.route.channel.connect_method if self.protocol.route.channel else f"open{self.func_name}"
        )

    def _group_slug(self) -> str:
        branch = self.router.group.branch.strip("/")
        if branch:
            return branch
        root = self.router.group.root.strip("/")
        return root or "root"

    def _ensure_model(self, model: Optional[Union[Type[Model], Model]], suffix: str) -> Optional[KotlinProto]:
        if model is None:
            return None
        auto_flag = getattr(model, "__auto__", False)
        is_route_model = auto_flag or isinstance(model, FieldWrappedModel)
        if auto_flag:
            name = f"{self.group_class.removesuffix('Api')}{self.func_name}{suffix}"
        else:
            name = getattr(model, "__name__", None) or f"{self.func_name}{suffix}"
        tag = "route" if is_route_model else "shared"
        module = self.group_slug if is_route_model else "shared"
        return self.registry.ensure(model, name=name, tag=tag, module=module)

    def _ensure_message_contract(self, contract: MessageContract | None, suffix: str) -> Optional[KotlinProto]:
        if contract is None:
            return None
        if contract.single_model is not None:
            return self._ensure_model(contract.single_model, suffix)
        for variant in contract.variants:
            self._ensure_model(variant.model, f"{suffix}{variant.key.capitalize()}")
        if contract.name:
            return KotlinMessageRef(contract.name)  # type: ignore[return-value]
        return self.registry.register_alias(
            contract.name or f"{self.group_class.removesuffix('Api')}{self.func_name}{suffix}",
            KotlinResolvedType("kotlinx.serialization.json.JsonElement"),
            tag="route",
            module=self.group_slug,
        )

    def message_helpers(self) -> tuple[KotlinMessageHelper, ...]:
        return self._message_helpers

    def _build_message_helpers(self) -> tuple[KotlinMessageHelper, ...]:
        helpers: list[KotlinMessageHelper] = []
        for contract, suffix in (
            (self.protocol.server_message, "ServerMessage"),
            (self.protocol.client_message, "ClientMessage"),
        ):
            if contract is None or not contract.is_union or contract.name is None or not contract.variants:
                continue
            variants: list[KotlinMessageVariant] = []
            for variant in contract.variants:
                proto = self._ensure_model(variant.model, f"{suffix}{variant.key.capitalize()}")
                if proto is None:
                    continue
                variants.append(
                    KotlinMessageVariant(
                        key=variant.key,
                        method_name=to_kotlin_property_name(variant.key),
                        data_type=proto.name,
                    )
                )
            if not variants:
                continue
            helpers.append(
                KotlinMessageHelper(
                    name=contract.name,
                    variants_object=f"{contract.name}Variants",
                    handlers_interface=f"{contract.name}Handlers",
                    dispatch_exception=f"{contract.name}DispatchException",
                    dispatch_func=f"dispatch{contract.name}",
                    variants=tuple(variants),
                )
            )
        return tuple(helpers)

    def _payload_response_type(self) -> KotlinResolvedType:
        if self.response_media_type != "application/json":
            return KotlinResolvedType("String", serializer="String.serializer()")
        if self.response_payload_proto is None:
            return KotlinResolvedType("Unit", serializer="Unit.serializer()")

        payload_name = self.response_payload_proto.name
        payload_deps: set[KotlinProto] = {self.response_payload_proto}
        payload_serializer = self.response_payload_proto.serializer_expr()

        return KotlinResolvedType(payload_name, payload_deps, serializer=payload_serializer)

@dataclass
class KotlinApiGroup:
    slug: str
    class_name: str
    property_name: str
    package_path: str
    package_suffix: str
    routes: list[KotlinRoute] = field(default_factory=list)

    def binary_schemas(self) -> list[KotlinBinarySchema]:
        schemas = [route.binary_schema for route in self.routes if route.binary_schema is not None]
        return unique_kotlin_binary_schemas(schemas)

    def message_helpers(self) -> tuple[KotlinMessageHelper, ...]:
        helpers: "OrderedDict[str, KotlinMessageHelper]" = OrderedDict()
        for route in self.routes:
            for helper in route.message_helpers():
                helpers.setdefault(helper.name, helper)
        return tuple(helpers.values())

    def query_map_protos(self) -> tuple[KotlinProto, ...]:
        protos: "OrderedDict[str, KotlinProto]" = OrderedDict()
        for route in self.routes:
            for proto in (route.query_proto, route.open_proto):
                if proto is not None and proto.fields:
                    protos.setdefault(proto.name, proto)
        return tuple(protos.values())


class KotlinBlueprint(BaseBlueprint["KotlinWriter"]):
    def __init__(self, writer: "KotlinWriter", bp):
        super().__init__(writer, bp)
        self.registry = KotlinProtoRegistry()
        self.routes: list[KotlinRoute] = []
        self.groups: "OrderedDict[str, KotlinApiGroup]" = OrderedDict()

    @property
    def root_package_path(self) -> str:
        return to_kotlin_package_path(self.bp.root, fallback="api")

    @property
    def root_package_suffix(self) -> str:
        return to_kotlin_package_suffix(self.bp.root, fallback="api")

    @property
    def root_package(self) -> str:
        return f"{self.writer.package}.{self.root_package_suffix}"

    def collect(self) -> None:
        self.routes = []
        self.groups = OrderedDict()
        selection = KotlinRouteSelection(include=self.writer.include, exclude=self.writer.exclude)
        for _group, router in self.iter_router():
            protocol = self.protocol_for_router(router)
            route_name = protocol.route.func_name
            if not selection.includes(router, route_name=route_name):
                continue
            self._register_common_models(protocol)
            route = KotlinRoute(router, self.registry, protocol=protocol)
            self.routes.append(route)
            group = self.groups.get(route.group_slug)
            if group is None:
                group_path = self._route_group_package_path(route.group_slug)
                group = KotlinApiGroup(
                    slug=route.group_slug,
                    class_name=route.group_class,
                    property_name=to_kotlin_property_name(route.group_slug),
                    package_path=to_kotlin_package_path(group_path),
                    package_suffix=to_kotlin_package_suffix(group_path),
                )
                self.groups[route.group_slug] = group
            group.routes.append(route)

    def _route_group_package_path(self, group_slug: str) -> str:
        root = self.bp.root.strip("/")
        group_path = group_slug.strip("/")
        if not root:
            return group_path
        if group_path == root or group_path.startswith(f"{root}/"):
            return group_path
        return f"{root}/{group_path}"

    def protocol_for_router(self, router: Router) -> RouteProtocolContract:
        return self.writer.route_protocol_for(router)

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
                if nested is model_cls:
                    continue
                if nested is FieldWrappedModel:
                    continue
                nested_auto = getattr(nested, "__auto__", False)
                if nested_auto:
                    continue
                self.registry.ensure(nested, tag="shared")
            model_auto = getattr(model, "__auto__", False)
            if not model_auto and getattr(model_cls, "__auto__", False) is False:
                self.registry.ensure(model_cls, tag="shared")

        collect(protocol.request.query.model)
        collect(protocol.request.open.model)
        collect(protocol.request.form.model)
        collect(protocol.request.json.model)
        collect(protocol.request.binary.model)
        collect(protocol.response.model.model)
        collect(protocol.close_model)
        if protocol.server_message is not None:
            for variant in protocol.server_message.variants:
                collect(variant.model)
        if protocol.client_message is not None:
            for variant in protocol.client_message.variants:
                collect(variant.model)
        for recv in protocol.recvs:
            collect(recv)
        for send in protocol.sends:
            collect(send)

    def group_model_imports(self, group_slug: str) -> list[str]:
        shared_names: set[str] = set()
        for proto in self.registry.filter(module=group_slug):
            for dep in proto.dependencies():
                if dep.module == "shared":
                    shared_names.add(dep.name)
        return sorted(shared_names)


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .writer import KotlinWriter


def _kotlin_string(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)
