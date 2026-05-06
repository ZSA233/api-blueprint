from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional, Type, Union

from api_blueprint.engine.model import FieldWrappedModel, Model, iter_field_model_type, unwrap_model_type
from api_blueprint.engine.router import Router
from api_blueprint.engine.utils import snake_to_pascal_case
from api_blueprint.engine.wrapper import NoneWrapper, ResponseWrapper
from api_blueprint.writer.core.base import BaseBlueprint
from api_blueprint.writer.core.contract_adapters import RouteProtocolContract, route_protocol_from_router

from .naming import to_kotlin_property_name, to_kotlin_type_name
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
        if self.protocol.route.supports_stream or self.protocol.route.supports_channel:
            raise ValueError(f"[kotlin-client] 暂不支持长连接 route: {self.url}")
        self.http_methods = list(self.protocol.route.http_methods)
        self.supports_ws = self.protocol.route.supports_ws
        if self.supports_ws:
            raise ValueError(f"[kotlin-client] 暂不支持 WebSocket route: {self.url}")
        if len(self.http_methods) != 1:
            raise ValueError(f"[kotlin-client] Kotlin 客户端要求每个 route 只有一个 HTTP method: {self.url}")

        self.query_proto = self._ensure_model(self.protocol.request.query.model, "Query")
        self.form_proto = self._ensure_model(self.protocol.request.form.model, "Form")
        self.json_proto = self._ensure_model(self.protocol.request.json.model, "Json")
        self.bin_proto = self.protocol.request.binary.model is not None
        if self.form_proto is not None or self.bin_proto:
            raise ValueError(f"[kotlin-client] 暂不支持 form/binary body route: {self.url}")

        self.response_media_type = self.protocol.response.media_type
        self.response_payload_proto = self._ensure_model(self.protocol.response.model.model, "Response")
        self.wrapper_proto = self._register_wrapper(self.protocol.response.wrapper)
        self.response_type = self._response_type()

    @property
    def http_method(self) -> str:
        return self.http_methods[0]

    @property
    def query_type(self) -> str | None:
        return self.query_proto.name if self.query_proto else None

    @property
    def json_type(self) -> str | None:
        return self.json_proto.name if self.json_proto else None

    @property
    def response_serializer_expr(self) -> str:
        return self.response_type.serializer_expr()

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
    routes: list[KotlinRoute] = field(default_factory=list)


class KotlinBlueprint(BaseBlueprint["KotlinWriter"]):
    def __init__(self, writer: "KotlinWriter", bp):
        super().__init__(writer, bp)
        self.registry = KotlinProtoRegistry()
        self.routes: list[KotlinRoute] = []
        self.groups: "OrderedDict[str, KotlinApiGroup]" = OrderedDict()

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
                group = KotlinApiGroup(
                    slug=route.group_slug,
                    class_name=route.group_class,
                    property_name=to_kotlin_property_name(route.group_slug),
                )
                self.groups[route.group_slug] = group
            group.routes.append(route)
        self._propagate_route_modules()

    def _propagate_route_modules(self) -> None:
        """Move auto-generated field-type models to the same module as their route parent."""
        for proto in self.registry.filter(module="shared"):
            if getattr(proto.model, "__auto__", False) and proto.tags <= {"shared"}:
                if not proto.fields and proto.kind != "data":
                    continue
                for route_group in self.groups:
                    route_protos = self.registry.filter(module=route_group)
                    for route_proto in route_protos:
                        if proto in route_proto.dependencies():
                            proto.module = route_group
                            proto.add_tag("route")
                            break

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
        collect(protocol.request.form.model)
        collect(protocol.request.json.model)
        collect(protocol.response.model.model)
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
