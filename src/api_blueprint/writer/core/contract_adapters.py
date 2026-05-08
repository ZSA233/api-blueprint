from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping

from api_blueprint.engine.connection import ConnectionKind, ConnectionScope, DefaultConnectionClose, MessageContract, ModelRef
from api_blueprint.engine.router import Router
from api_blueprint.engine.utils import snake_to_pascal_case
from api_blueprint.engine.wrapper import NoneWrapper, ResponseWrapper
from api_blueprint.writer.core.contracts import ConnectionBridgeContract, RouteContract, WsBridgeContract, route_id_for_router

if TYPE_CHECKING:
    from api_blueprint.contract import ContractGraph


ManifestRoute = Mapping[str, Any]
ManifestService = Mapping[str, Any]


@dataclass(frozen=True)
class RouteRuntimeSnapshot:
    query_model: ModelRef | None
    json_model: ModelRef | None
    form_model: ModelRef | None
    binary_model: ModelRef | None
    open_model: ModelRef | None
    response_model: ModelRef | None
    response_media_type: str
    response_wrapper: type[ResponseWrapper]
    recvs: tuple[ModelRef, ...]
    sends: tuple[ModelRef, ...]
    server_message: MessageContract | None
    client_message: MessageContract | None
    close_model: ModelRef | None


@dataclass(frozen=True)
class RouteModelSlot:
    schema: str | None
    model: ModelRef | None


@dataclass(frozen=True)
class RouteRequestContract:
    query: RouteModelSlot
    json: RouteModelSlot
    form: RouteModelSlot
    binary: RouteModelSlot
    open: RouteModelSlot


@dataclass(frozen=True)
class RouteResponseContract:
    media_type: str
    model: RouteModelSlot
    wrapper: type[ResponseWrapper]


@dataclass(frozen=True)
class RouteProtocolContract:
    route: RouteContract
    request: RouteRequestContract
    response: RouteResponseContract
    recvs: tuple[ModelRef, ...]
    sends: tuple[ModelRef, ...]
    server_message: MessageContract | None
    client_message: MessageContract | None
    close_model: ModelRef | None


@dataclass(frozen=True)
class RouteContractIndex:
    routes: dict[str, ManifestRoute]
    services: dict[str, ManifestService]
    route_runtime: dict[str, Any]

    @classmethod
    def from_graph(cls, graph: ContractGraph) -> "RouteContractIndex":
        manifest = graph.to_manifest()
        routes: dict[str, ManifestRoute] = {}
        for route in manifest.get("routes", []):
            if not isinstance(route, Mapping):
                continue
            route_id = route.get("id")
            if isinstance(route_id, str):
                routes[route_id] = route
        services = {
            str(service["id"]): service
            for service in manifest.get("services", [])
            if isinstance(service, Mapping) and isinstance(service.get("id"), str)
        }
        return cls(routes=routes, services=services, route_runtime=dict(graph.route_runtime))

    def for_router(self, router: Router, *, close_model: ModelRef | None = None) -> RouteContract:
        return self.protocol_for_router(router, close_model=close_model).route

    def protocol_for_router(self, router: Router, *, close_model: ModelRef | None = None) -> RouteProtocolContract:
        route_id = route_id_for_router(router)
        route = self.routes.get(route_id)
        if route is None:
            kind = _router_kind(router)
            raise KeyError(f"ContractGraph route not found for {route_id} ({kind} {router.url})")
        service_id = str(route.get("service_id") or "")
        service = self.services.get(service_id)
        if service is None:
            raise KeyError(f"ContractGraph service not found for route {route.get('id')}: {service_id}")
        runtime = self.route_runtime.get(route_id) or _runtime_from_router(router)
        return route_protocol_from_manifest(route, service, runtime, close_model=close_model)


def route_protocol_from_router(
    router: Router,
    *,
    contract: RouteContract | None = None,
) -> RouteProtocolContract:
    runtime = _runtime_from_router(router)
    contract = contract or route_contract_from_router(router)
    return _route_protocol_from_contract(contract, _manifest_from_router(router), runtime)


def route_contract_from_router(router: Router) -> RouteContract:
    from api_blueprint.writer.core.contracts import route_contract

    return route_contract(router)


def route_protocol_from_manifest(
    route: ManifestRoute,
    service: ManifestService,
    runtime: Any,
    *,
    close_model: ModelRef | None = None,
) -> RouteProtocolContract:
    resolved_close_model = close_model if close_model is not None else runtime.close_model
    contract = route_contract_from_manifest(route, service, close_model=resolved_close_model)
    return _route_protocol_from_contract(contract, route, runtime)


def route_contract_from_manifest(
    route: ManifestRoute,
    service: ManifestService,
    *,
    close_model: ModelRef | None = None,
) -> RouteContract:
    route_id = str(route["id"])
    func_name = str(route["operation"])
    method_name = str(route.get("method_name") or _to_camel(func_name))
    group_alias = _slug(str(service.get("group") or "root"), default="root")
    group_slug = group_alias
    group_prefix = _prefix(group_alias)
    group_pascal = snake_to_pascal_case(group_slug, "", "Group")
    client_class = _suffix(snake_to_pascal_case(group_alias or "root", "", "Group"), "Client")
    service_name = str(service.get("name") or _suffix(snake_to_pascal_case(group_alias or "root", "", "Group"), "Service"))
    kind = str(route.get("kind") or "rpc")
    connection_scope = _connection_scope(route)
    methods = tuple(
        str(method)
        for method in route.get("methods", [])
        if str(method) in {"GET", "POST", "PUT", "DELETE", "HEAD"}
    )

    ws = None
    if kind == ConnectionKind.LEGACY_WS.value:
        event_base = f"api_blueprint.ws.{route_id}"
        ws = WsBridgeContract(
            route_id=route_id,
            connect_method=f"Connect{func_name}",
            connect_raw_method=f"Connect{func_name}Raw",
            send_method=f"Send{func_name}",
            close_method=f"Close{func_name}",
            event_base=event_base,
            message_event_prefix=f"{event_base}.message",
            close_event_prefix=f"{event_base}.closed",
        )

    stream = None
    if kind == ConnectionKind.STREAM.value:
        event_base = f"api_blueprint.stream.{route_id}"
        bridge_close_model = close_model or DefaultConnectionClose
        stream = ConnectionBridgeContract(
            route_id=route_id,
            kind=ConnectionKind.STREAM,
            scope=connection_scope or ConnectionScope.SESSION,
            close_model=bridge_close_model,
            connect_method=f"Subscribe{func_name}",
            close_method=f"Close{func_name}",
            event_base=event_base,
            message_event_prefix=f"{event_base}.message",
            close_event_prefix=f"{event_base}.closed",
        )

    channel = None
    if kind == ConnectionKind.CHANNEL.value:
        event_base = f"api_blueprint.channel.{route_id}"
        bridge_close_model = close_model or DefaultConnectionClose
        channel = ConnectionBridgeContract(
            route_id=route_id,
            kind=ConnectionKind.CHANNEL,
            scope=connection_scope or ConnectionScope.SESSION,
            close_model=bridge_close_model,
            connect_method=f"Open{func_name}",
            send_method=f"Send{func_name}",
            close_method=f"Close{func_name}",
            event_base=event_base,
            message_event_prefix=f"{event_base}.message",
            close_event_prefix=f"{event_base}.closed",
        )

    return RouteContract(
        route_id=route_id,
        func_name=func_name,
        method_name=method_name,
        group_slug=group_slug,
        group_alias=group_alias,
        group_prefix=group_prefix,
        group_pascal=group_pascal,
        group_package=group_alias,
        client_class=client_class,
        service_name=service_name,
        namespace=group_alias,
        http_methods=methods,
        supports_ws=kind == ConnectionKind.LEGACY_WS.value,
        supports_stream=kind == ConnectionKind.STREAM.value,
        supports_channel=kind == ConnectionKind.CHANNEL.value,
        connection_scope=connection_scope,
        connection_close_model=close_model,
        url=str(route.get("url") or ""),
        ws=ws,
        stream=stream,
        channel=channel,
    )


def _route_protocol_from_contract(
    contract: RouteContract,
    route: ManifestRoute,
    runtime: Any,
) -> RouteProtocolContract:
    request_manifest = _mapping(route.get("request"))
    response_manifest = _mapping(route.get("response"))
    return RouteProtocolContract(
        route=contract,
        request=RouteRequestContract(
            query=RouteModelSlot(_optional_str(request_manifest.get("query_model")), runtime.query_model),
            json=RouteModelSlot(_optional_str(request_manifest.get("json_model")), runtime.json_model),
            form=RouteModelSlot(_optional_str(request_manifest.get("form_model")), runtime.form_model),
            binary=RouteModelSlot(_optional_str(request_manifest.get("binary_model")), runtime.binary_model),
            open=RouteModelSlot(_connection_schema(route, "open_model"), runtime.open_model),
        ),
        response=RouteResponseContract(
            media_type=str(response_manifest.get("media_type") or runtime.response_media_type or "application/json"),
            model=RouteModelSlot(_optional_str(response_manifest.get("model")), runtime.response_model),
            wrapper=runtime.response_wrapper or NoneWrapper,
        ),
        recvs=tuple(runtime.recvs),
        sends=tuple(runtime.sends),
        server_message=runtime.server_message,
        client_message=runtime.client_message,
        close_model=runtime.close_model,
    )


def _runtime_from_router(router: Router) -> RouteRuntimeSnapshot:
    return RouteRuntimeSnapshot(
        query_model=router.req_query,
        json_model=router.req_json,
        form_model=router.req_form,
        binary_model=router.req_bin,
        open_model=router.open_model,
        response_model=router.rsp_model,
        response_media_type=router.rsp_media_type,
        response_wrapper=router.response_wrapper,
        recvs=tuple(router.recvs),
        sends=tuple(router.sends),
        server_message=router.server_message,
        client_message=router.client_message,
        close_model=router.effective_close_model,
    )


def _manifest_from_router(router: Router) -> ManifestRoute:
    return {
        "request": {},
        "response": {"media_type": router.rsp_media_type},
        "connection": None,
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _connection_schema(route: ManifestRoute, key: str) -> str | None:
    connection = route.get("connection")
    if not isinstance(connection, Mapping):
        return None
    return _optional_str(connection.get(key))


def _router_kind(router: Router) -> str:
    if router.connection_kind == ConnectionKind.RPC:
        return "rpc"
    return router.connection_kind.value


def _connection_scope(route: ManifestRoute) -> ConnectionScope | None:
    connection = route.get("connection")
    if not isinstance(connection, Mapping):
        return None
    value = connection.get("scope")
    if not isinstance(value, str):
        return None
    return ConnectionScope(value)


def _slug(value: str, *, default: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z]+", "_", value.lower()).strip("_")
    return normalized or default


def _prefix(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "_", value).strip("_").upper() or "ROOT"


def _suffix(value: str, suffix: str) -> str:
    return value if value.endswith(suffix) else f"{value}{suffix}"


def _to_camel(name: str) -> str:
    if not name:
        return name
    return name[0].lower() + name[1:]
