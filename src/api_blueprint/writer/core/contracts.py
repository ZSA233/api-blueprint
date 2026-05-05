from __future__ import annotations

import re
from dataclasses import dataclass

from api_blueprint.engine.router import Router
from api_blueprint.engine.utils import snake_to_pascal_case
from api_blueprint.writer.typescript.naming import to_camel


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
    url: str
    ws: WsBridgeContract | None = None


def route_contract(router: Router) -> RouteContract:
    func_name = _func_name(router.leaf)
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
    route_method_slug = _slug(",".join(sorted(method.lower() for method in router.methods)), default="route")
    route_name_slug = _slug(func_name, default="root")
    route_id = ".".join((root_slug, group_alias, route_method_slug, route_name_slug))
    supports_ws = any(method == "WS" for method in router.methods)
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
        http_methods=tuple(method for method in router.methods if method != "WS"),
        supports_ws=supports_ws,
        url=router.url,
        ws=ws,
    )


def _func_name(leaf: str) -> str:
    if not leaf.strip("/"):
        return "Root"
    return snake_to_pascal_case(leaf, "", "Z")


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
