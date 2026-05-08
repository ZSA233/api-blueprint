from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional, Type, Union

from api_blueprint.engine.model import FieldWrappedModel, Model, iter_field_model_type, unwrap_model_type
from api_blueprint.engine.router import Router
from api_blueprint.engine.utils import snake_to_pascal_case
from api_blueprint.engine.wrapper import NoneWrapper, ResponseWrapper
from api_blueprint.writer.core.base import BaseBlueprint
from api_blueprint.engine.connection import MessageContract
from api_blueprint.writer.core.contract_adapters import RouteProtocolContract, route_protocol_from_router

from .naming import to_kotlin_package_path, to_kotlin_package_suffix, to_kotlin_property_name, to_kotlin_type_name
from .protos import KotlinProto, KotlinProtoRegistry, KotlinResolvedType
from .selection import KotlinRouteSelection


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
        self.func_name = self._func_name()
        self.method_name = to_kotlin_property_name(self.func_name)
        self.group_slug = self.protocol.route.group_slug
        self.group_class = to_kotlin_type_name(self.group_slug, fallback="Root") + "Api"
        self.url = self.protocol.route.url
        self.http_methods = list(self.protocol.route.http_methods)
        self.supports_ws = self.protocol.route.supports_ws
        self.supports_stream = self.protocol.route.supports_stream
        self.supports_channel = self.protocol.route.supports_channel
        if self.is_rpc and len(self.http_methods) != 1:
            raise ValueError(f"[kotlin-client] Kotlin 客户端要求每个 route 只有一个 HTTP method: {self.url}")

        self.query_proto = self._ensure_model(self.protocol.request.query.model, "Query")
        self.open_proto = self._ensure_model(self.protocol.request.open.model, "Open")
        self.form_proto = self._ensure_model(self.protocol.request.form.model, "Form")
        self.json_proto = self._ensure_model(self.protocol.request.json.model, "Json")
        self.binary_proto = self._ensure_model(self.protocol.request.binary.model, "Binary")

        self.response_media_type = self.protocol.response.media_type
        self.response_payload_proto = self._ensure_model(self.protocol.response.model.model, "Response")
        self.wrapper_proto = self._register_wrapper(self.protocol.response.wrapper)
        self.response_type = self._response_type()
        self.ws_recv_proto = self._ensure_message_contract(self.protocol.server_message, "WsRecv")
        self.ws_send_proto = self._ensure_message_contract(self.protocol.client_message, "WsSend")
        if self.supports_ws:
            self.ws_recv_proto = self._ensure_ws_models(self.protocol.recvs, "WsRecv") or self.ws_recv_proto
            self.ws_send_proto = self._ensure_ws_models(self.protocol.sends, "WsSend") or self.ws_send_proto
        self.server_message_proto = self._ensure_message_contract(self.protocol.server_message, "ServerMessage")
        self.client_message_proto = self._ensure_message_contract(self.protocol.client_message, "ClientMessage")
        self.close_proto = self._ensure_model(self.protocol.close_model, "Close")

    @property
    def is_rpc(self) -> bool:
        return not (self.supports_ws or self.supports_stream or self.supports_channel)

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
        return self.binary_proto.name if self.binary_proto else None

    @property
    def response_serializer_expr(self) -> str:
        return self.response_type.serializer_expr()

    @property
    def ws_recv_type(self) -> str:
        return self.ws_recv_proto.name if self.ws_recv_proto else "kotlinx.serialization.json.JsonElement"

    @property
    def ws_send_type(self) -> str:
        return self.ws_send_proto.name if self.ws_send_proto else "kotlinx.serialization.json.JsonElement"

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
    def connect_method_name(self) -> str:
        return to_kotlin_property_name(self.protocol.route.ws.connect_method if self.protocol.route.ws else f"connect{self.func_name}")

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

    def _func_name(self) -> str:
        if not self.router.leaf.strip("/"):
            return "Root"
        return snake_to_pascal_case(self.router.leaf, "", "Func")

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

    def _ensure_ws_models(
        self,
        models: tuple[Union[Type[Model], Model], ...],
        suffix: str,
    ) -> Optional[KotlinProto]:
        if not models:
            return None
        if len(models) == 1:
            return self._ensure_model(models[0], suffix)
        return self.registry.register_alias(
            f"{self.group_class.removesuffix('Api')}{self.func_name}{suffix}",
            KotlinResolvedType("kotlinx.serialization.json.JsonElement"),
            tag="route",
            module=self.group_slug,
        )

    def _ensure_message_contract(self, contract: MessageContract | None, suffix: str) -> Optional[KotlinProto]:
        if contract is None:
            return None
        if contract.single_model is not None:
            return self._ensure_model(contract.single_model, suffix)
        for variant in contract.variants:
            self._ensure_model(variant.model, f"{suffix}{variant.key.capitalize()}")
        return self.registry.register_alias(
            contract.name or f"{self.group_class.removesuffix('Api')}{self.func_name}{suffix}",
            KotlinResolvedType("kotlinx.serialization.json.JsonElement"),
            tag="route",
            module=self.group_slug,
        )

    def _register_wrapper(self, wrapper_cls: type[ResponseWrapper]) -> Optional[KotlinProto]:
        wrapper_cls = wrapper_cls or NoneWrapper
        if wrapper_cls is NoneWrapper:
            return None
        return self.registry.register_wrapper(wrapper_cls)

    def _response_type(self) -> KotlinResolvedType:
        if self.response_media_type != "application/json":
            return KotlinResolvedType("String", serializer="String.serializer()")
        if self.response_payload_proto is None:
            return KotlinResolvedType("Unit", serializer="Unit.serializer()")

        payload_name = self.response_payload_proto.name
        payload_deps: set[KotlinProto] = {self.response_payload_proto}
        payload_serializer = self.response_payload_proto.serializer_expr()

        if self.wrapper_proto is not None:
            wrapper_name = self.wrapper_proto.name
            return KotlinResolvedType(
                f"{wrapper_name}<{payload_name}>",
                payload_deps | {self.wrapper_proto},
                serializer=f"{wrapper_name}.serializer({payload_serializer})",
            )

        return KotlinResolvedType(payload_name, payload_deps, serializer=payload_serializer)


@dataclass
class KotlinApiGroup:
    slug: str
    class_name: str
    property_name: str
    package_path: str
    package_suffix: str
    routes: list[KotlinRoute] = field(default_factory=list)


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
            route_name = snake_to_pascal_case(router.leaf or "root", "", "Func")
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
