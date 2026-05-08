from __future__ import annotations

import re
from dataclasses import dataclass

from api_blueprint.engine.connection import ConnectionKind, ConnectionScope, ModelRef
from api_blueprint.engine.router import Router
from api_blueprint.engine.utils import snake_to_pascal_case


@dataclass(frozen=True)
class WsBridgeContract:
    route_id: str
    connect_method: str
    connect_raw_method: str
    send_method: str
    close_method: str
    event_base: str
    message_event_prefix: str
    close_event_prefix: str


@dataclass(frozen=True)
class ConnectionBridgeContract:
    route_id: str
    kind: ConnectionKind
    scope: ConnectionScope
    close_model: ModelRef
    connect_method: str
    close_method: str
    event_base: str
    message_event_prefix: str
    close_event_prefix: str
    send_method: str | None = None


@dataclass(frozen=True)
class RouteContract:
    route_id: str
    func_name: str
    method_name: str
    group_slug: str
    group_alias: str
    group_prefix: str
    group_pascal: str
    group_package: str
    client_class: str
    service_name: str
    namespace: str
    http_methods: tuple[str, ...]
    supports_ws: bool
    supports_stream: bool
    supports_channel: bool
    connection_scope: ConnectionScope | None
    connection_close_model: ModelRef | None
    url: str
    ws: WsBridgeContract | None = None
    stream: ConnectionBridgeContract | None = None
    channel: ConnectionBridgeContract | None = None


def route_contract(router: Router) -> RouteContract:
    func_name = _operation_name(router)
    group_slug = _group_slug(router)
    group_alias = _group_alias(router)
    group_prefix = _group_prefix(router)
    group_pascal = snake_to_pascal_case(group_slug, "", "Group")
    client_class = snake_to_pascal_case(group_alias or "root", "", "Group")
    if not client_class.endswith("Client"):
        client_class += "Client"
    service_name = snake_to_pascal_case(group_alias or "root", "", "Group")
    if not service_name.endswith("Service"):
        service_name += "Service"

    root_slug = _slug((router.group.bp.root or "").strip("/"), default="root")
    route_method_slug = _route_method_slug(router)
    route_name_slug = _slug(_func_name(router.leaf), default="root")
    route_id = ".".join((root_slug, group_alias, route_method_slug, route_name_slug))
    supports_ws = router.connection_kind == ConnectionKind.LEGACY_WS
    supports_stream = router.connection_kind == ConnectionKind.STREAM
    supports_channel = router.connection_kind == ConnectionKind.CHANNEL
    connection_close_model = router.effective_close_model
    if (supports_stream or supports_channel) and connection_close_model is None:
        raise RuntimeError(f"connection route[{router.url}] does not have an effective close model")
    ws = None
    if supports_ws:
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
    if supports_stream:
        event_base = f"api_blueprint.stream.{route_id}"
        stream = ConnectionBridgeContract(
            route_id=route_id,
            kind=ConnectionKind.STREAM,
            scope=router.connection_scope or ConnectionScope.SESSION,
            close_model=connection_close_model,
            connect_method=f"Subscribe{func_name}",
            close_method=f"Close{func_name}",
            event_base=event_base,
            message_event_prefix=f"{event_base}.message",
            close_event_prefix=f"{event_base}.closed",
        )
    channel = None
    if supports_channel:
        event_base = f"api_blueprint.channel.{route_id}"
        channel = ConnectionBridgeContract(
            route_id=route_id,
            kind=ConnectionKind.CHANNEL,
            scope=router.connection_scope or ConnectionScope.SESSION,
            close_model=connection_close_model,
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
        method_name=to_camel(func_name),
        group_slug=group_slug,
        group_alias=group_alias,
        group_prefix=group_prefix,
        group_pascal=group_pascal,
        group_package=group_alias,
        client_class=client_class,
        service_name=service_name,
        namespace=group_alias,
        http_methods=tuple(method for method in router.methods if method in {"GET", "POST", "PUT", "DELETE", "HEAD"}),
        supports_ws=supports_ws,
        supports_stream=supports_stream,
        supports_channel=supports_channel,
        connection_scope=router.connection_scope,
        connection_close_model=connection_close_model,
        url=router.url,
        ws=ws,
        stream=stream,
        channel=channel,
    )


def _func_name(leaf: str) -> str:
    if not leaf.strip("/"):
        return "Root"
    return snake_to_pascal_case(leaf, "", "Z")


def _operation_name(router: Router) -> str:
    operation_id = router.extra.get("operation_id")
    if isinstance(operation_id, str) and operation_id.strip():
        return snake_to_pascal_case(operation_id.strip(), "", "Z")
    return _func_name(router.leaf)


def _group_prefix(router: Router) -> str:
    branch = (router.group.branch or "").strip("/")
    if branch:
        return re.sub(r"[^0-9A-Za-z]+", "_", branch).upper()
    root = (router.group.root or "").strip("/")
    if root:
        return re.sub(r"[^0-9A-Za-z]+", "_", root).upper()
    return "ROOT"


def _group_slug(router: Router) -> str:
    branch = (router.group.branch or "").strip("/")
    if branch:
        slug = re.sub(r"[^0-9A-Za-z]+", "_", branch.lower()) or "root"
    else:
        root = (router.group.root or "").strip("/")
        slug = re.sub(r"[^0-9A-Za-z]+", "_", root.lower()) or "root" if root else "root"
    return slug


def _group_alias(router: Router) -> str:
    branch = (router.group.branch or "").strip("/")
    if branch:
        alias = re.sub(r"[^0-9A-Za-z]+", "_", branch.lower()) or "root"
    else:
        root = (router.group.root or "").strip("/")
        alias = re.sub(r"[^0-9A-Za-z]+", "_", root.lower()) or "root" if root else "root"
    return alias


def _slug(value: str, *, default: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z]+", "_", value.lower()).strip("_")
    return normalized or default


def _route_method_slug(router: Router) -> str:
    if router.connection_kind == ConnectionKind.STREAM:
        return "stream"
    if router.connection_kind == ConnectionKind.CHANNEL:
        return "channel"
    return _slug(",".join(sorted(method.lower() for method in router.methods)), default="route")


def to_camel(name: str) -> str:
    if not name:
        return name
    return name[0].lower() + name[1:]
