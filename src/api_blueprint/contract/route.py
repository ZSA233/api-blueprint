from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence

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
    return _build_route_contract(router, func_name=_operation_name(router))


def route_id_for_router(router: Router) -> str:
    return _route_id(router, root_slug=_root_slug(router), group_alias=_group_alias(router))


def resolve_route_contracts(routers: Sequence[Router]) -> dict[Router, RouteContract]:
    candidates_by_scope: dict[tuple[str, str], list[_RouteOperationCandidate]] = defaultdict(list)
    for router in routers:
        root_slug = _root_slug(router)
        group_alias = _group_alias(router)
        candidates_by_scope[(root_slug, group_alias)].append(
            _RouteOperationCandidate(
                router=router,
                scope=(root_slug, group_alias),
                route_id=_route_id(router, root_slug=root_slug, group_alias=group_alias),
                base_name=_operation_name(router),
                explicit_name=_has_explicit_operation_id(router),
                disambiguator=_operation_disambiguator(router),
            )
        )

    resolved: dict[Router, RouteContract] = {}
    for candidates in candidates_by_scope.values():
        names = _resolve_operation_names(candidates)
        for candidate in candidates:
            resolved[candidate.router] = _build_route_contract(
                candidate.router,
                func_name=names[candidate.router],
                route_id=candidate.route_id,
            )
    return resolved


def _build_route_contract(
    router: Router,
    *,
    func_name: str,
    route_id: str | None = None,
) -> RouteContract:
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

    route_id = route_id or route_id_for_router(router)
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
        return _normalize_operation_id(operation_id.strip(), invalid_prefix="Z")
    return _func_name(router.leaf)


def _has_explicit_operation_id(router: Router) -> bool:
    operation_id = router.extra.get("operation_id")
    return isinstance(operation_id, str) and bool(operation_id.strip())


def _normalize_operation_id(value: str, *, invalid_prefix: str) -> str:
    segments = value.split("/")
    normalized_segments: list[str] = []

    for segment in segments:
        if not segment:
            continue
        parts = re.split(r"[^0-9A-Za-z]+", segment)
        normalized = "".join(_pascalize_token(part) for part in parts if part)
        if not normalized:
            normalized = invalid_prefix
        if not normalized[0].isalpha():
            normalized = invalid_prefix + normalized
        normalized = re.sub(r"[^0-9A-Za-z_]", "", normalized)
        normalized_segments.append(normalized)

    name = "_".join(normalized_segments)
    if not name:
        name = invalid_prefix
    if not name[0].isalpha():
        name = invalid_prefix + name
    return name


def _pascalize_token(token: str) -> str:
    if not token:
        return token
    return token[:1].upper() + token[1:]


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


def _root_slug(router: Router) -> str:
    return _slug((router.group.bp.root or "").strip("/"), default="root")


def _route_id(router: Router, *, root_slug: str, group_alias: str) -> str:
    route_method_slug = _route_method_slug(router)
    route_name_slug = _slug(_func_name(router.leaf), default="root")
    return ".".join((root_slug, group_alias, route_method_slug, route_name_slug))


def _route_method_slug(router: Router) -> str:
    if router.connection_kind == ConnectionKind.STREAM:
        return "stream"
    if router.connection_kind == ConnectionKind.CHANNEL:
        return "channel"
    return _slug(",".join(sorted(method.lower() for method in router.methods)), default="route")


def _operation_disambiguator(router: Router) -> str:
    if router.connection_kind == ConnectionKind.LEGACY_WS:
        return "Ws"
    if router.connection_kind == ConnectionKind.STREAM:
        return "Stream"
    if router.connection_kind == ConnectionKind.CHANNEL:
        return "Channel"

    http_methods = [method for method in router.methods if method in _HTTP_METHOD_DISAMBIGUATORS]
    if http_methods:
        ordered = sorted(http_methods)
        return "".join(_HTTP_METHOD_DISAMBIGUATORS[method] for method in ordered)
    return "Route"


def to_camel(name: str) -> str:
    if not name:
        return name
    return name[0].lower() + name[1:]


@dataclass(frozen=True)
class _RouteOperationCandidate:
    router: Router
    scope: tuple[str, str]
    route_id: str
    base_name: str
    explicit_name: bool
    disambiguator: str


_HTTP_METHOD_DISAMBIGUATORS: dict[str, str] = {
    "DELETE": "Delete",
    "GET": "Get",
    "HEAD": "Head",
    "POST": "Post",
    "PUT": "Put",
}


def _resolve_operation_names(candidates: Sequence[_RouteOperationCandidate]) -> dict[Router, str]:
    resolved: dict[Router, str] = {}
    used_names: dict[str, _RouteOperationCandidate] = {}

    explicit_by_name: dict[str, list[_RouteOperationCandidate]] = defaultdict(list)
    auto_by_name: dict[str, list[_RouteOperationCandidate]] = defaultdict(list)
    for candidate in candidates:
        if candidate.explicit_name:
            explicit_by_name[candidate.base_name].append(candidate)
        else:
            auto_by_name[candidate.base_name].append(candidate)

    for name, items in explicit_by_name.items():
        if len(items) > 1:
            raise ValueError(_duplicate_operation_message(name, items))
        resolved[items[0].router] = name
        used_names[name] = items[0]

    unresolved: list[_RouteOperationCandidate] = []
    for name, items in auto_by_name.items():
        if len(items) == 1 and name not in used_names:
            resolved[items[0].router] = name
            used_names[name] = items[0]
            continue
        unresolved.extend(items)

    for candidate in unresolved:
        for proposed in (
            f"{candidate.base_name}{candidate.disambiguator}",
            f"{candidate.disambiguator}{candidate.base_name}",
        ):
            if proposed in used_names:
                continue
            resolved[candidate.router] = proposed
            used_names[proposed] = candidate
            break
        else:
            raise ValueError(_auto_operation_collision_message(candidate, used_names))

    return resolved


def _duplicate_operation_message(name: str, candidates: Sequence[_RouteOperationCandidate]) -> str:
    scope = ".".join(candidates[0].scope)
    routes = ", ".join(_candidate_summary(candidate) for candidate in candidates)
    return (
        f"duplicate operation name '{name}' in service[{scope}] for routes: {routes}. "
        "Set unique operation_id values for the conflicting routes."
    )


def _auto_operation_collision_message(
    candidate: _RouteOperationCandidate,
    used_names: dict[str, _RouteOperationCandidate],
) -> str:
    scope = ".".join(candidate.scope)
    conflicting = [
        name
        for name in (
            candidate.base_name,
            f"{candidate.base_name}{candidate.disambiguator}",
            f"{candidate.disambiguator}{candidate.base_name}",
        )
        if name in used_names
    ]
    names = ", ".join(conflicting) if conflicting else candidate.base_name
    return (
        f"could not derive a unique operation name for route {_candidate_summary(candidate)} in service[{scope}]. "
        f"Tried names: {names}. Set an explicit unique operation_id for this route."
    )


def _candidate_summary(candidate: _RouteOperationCandidate) -> str:
    methods = ",".join(method for method in candidate.router.methods if method) or candidate.router.connection_kind.value
    return f"{candidate.route_id} [{methods} {candidate.router.url}]"
