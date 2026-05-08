from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from api_blueprint.engine.model import Model
from api_blueprint.engine.router import Router
from api_blueprint.writer.core.base import BaseBlueprint
from api_blueprint.writer.core.contract_adapters import RouteProtocolContract

from .naming import to_path_segments, to_py_class_name, to_py_identifier

if TYPE_CHECKING:
    from .writer import PythonBaseWriter


@dataclass(frozen=True)
class PythonRequestParam:
    name: str
    call_name: str


class PythonRoute:
    def __init__(self, router: Router, protocol: RouteProtocolContract):
        self.router = router
        self.protocol = protocol
        self.contract = protocol.route
        self.method_name = to_py_identifier(self.contract.method_name, default="call")
        self.url = self.contract.url
        self.http_methods = tuple(self.contract.http_methods or ("GET",))
        self.response_type = _model_name(protocol.response.model.model)
        self.params = self._request_params()

    @property
    def is_rpc(self) -> bool:
        return not (self.supports_ws or self.supports_stream or self.supports_channel)

    @property
    def supports_ws(self) -> bool:
        return self.contract.supports_ws

    @property
    def supports_stream(self) -> bool:
        return self.contract.supports_stream

    @property
    def supports_channel(self) -> bool:
        return self.contract.supports_channel

    @property
    def connect_method_name(self) -> str:
        method = self.contract.ws.connect_method if self.contract.ws is not None else f"connect_{self.method_name}"
        return to_py_identifier(method, default=f"connect_{self.method_name}")

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
        if self.supports_ws:
            return json.dumps("legacy_ws")
        if self.supports_stream:
            return json.dumps("stream")
        if self.supports_channel:
            return json.dumps("channel")
        return json.dumps("rpc")

    @property
    def route_id_literal(self) -> str:
        return json.dumps(self.contract.route_id)

    @property
    def websocket_endpoint_name(self) -> str:
        if self.supports_channel:
            return f"{self.open_channel_method_name}_socket"
        return f"{self.connect_method_name}_socket"

    @property
    def response_type_literal(self) -> str:
        if self.response_type is None:
            return "None"
        return repr(self.response_type)

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
            params.append(PythonRequestParam("query", "query"))
        if self.protocol.request.json.model is not None:
            params.append(PythonRequestParam("json", "json"))
        if self.protocol.request.form.model is not None:
            params.append(PythonRequestParam("form", "form"))
        if self.protocol.request.binary.model is not None:
            params.append(PythonRequestParam("binary", "binary"))
        if self.protocol.request.open.model is not None:
            params.append(PythonRequestParam("open_data", "open_data"))
        return params


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
            route = PythonRoute(router, protocol)
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
