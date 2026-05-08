from __future__ import annotations

import pytest

from api_blueprint.contract import build_contract_graph
from api_blueprint.config.resolved import ResolvedApiTargetConfig
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import Model, String
from api_blueprint.writer.core.planning import (
    capability_errors,
    route_matches_rule,
    target_selects_route,
    target_capability_manifest,
)


class Event(Model):
    value = String(description="value")


def _route(url: str, *, route_id: str = "api.demo.get.ping") -> dict[str, object]:
    return {
        "id": route_id,
        "service_id": "api.demo",
        "kind": "rpc",
        "operation": "Ping",
        "methods": ["GET"],
        "url": url,
    }


def test_manifest_selection_uses_path_for_unprefixed_rules() -> None:
    route = _route("/api/demo/ping", route_id="api.demo.get.ping")
    target = ResolvedApiTargetConfig(
        id="kotlin.client",
        kind="kotlin-client",
        include=("/api/demo/*",),
        exclude=("api.demo.*",),
    )

    assert route_matches_rule(route, "/api/demo/*")
    assert not route_matches_rule(route, "api.demo.*")
    assert target_selects_route(target, route)


def test_kotlin_capability_accepts_connection_routes() -> None:
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.STREAM("/events").SERVER_MESSAGE(Event)
        views.CHANNEL("/chat").SERVER_MESSAGE(Event).CLIENT_MESSAGE(Event)
        views.WS("/ws").SEND(Event).RECV(Event)

    graph = build_contract_graph([bp])
    target = ResolvedApiTargetConfig(id="kotlin.client", kind="kotlin-client", out_dir=None, package="com.example")

    assert capability_errors(graph, (target,)) == []


def test_capability_validation_checks_only_declared_dimensions() -> None:
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.WS("/ws").SEND(Event).RECV(Event)

    graph = build_contract_graph([bp])
    target = ResolvedApiTargetConfig(id="grpc.proto", kind="grpc-proto", out_dir=None, package="example.api")

    assert capability_errors(graph, (target,)) == []

    class FakeGraph:
        def to_manifest(self) -> dict[str, object]:
            return {
                "routes": [
                    {
                        "id": "api.demo.future.route",
                        "service_id": "api.demo",
                        "kind": "future",
                        "operation": "Future",
                        "methods": ["GET"],
                        "url": "/api/demo/future",
                        "request": {"query_model": "Query"},
                        "response": {"wrapper": "NoneWrapper"},
                    }
                ]
            }

    assert capability_errors(FakeGraph(), (target,)) == [
        "grpc-proto does not support future route: api.demo.future.route"
    ]


def test_grpc_proto_capability_ignores_legacy_ws_without_advertising_output_support() -> None:
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.WS("/ws").SEND(Event).RECV(Event)

    graph = build_contract_graph([bp])
    target = ResolvedApiTargetConfig(id="grpc.proto", kind="grpc-proto", out_dir=None, package="example.api")
    manifest = target_capability_manifest()

    assert "legacy_ws" not in manifest["grpc-proto"]["routes"]
    assert manifest["grpc-proto"]["ignored_routes"] == ["legacy_ws"]
    assert capability_errors(graph, (target,)) == []


@pytest.mark.parametrize("kind", ["python-client", "python-server"])
def test_python_targets_are_real_generation_capabilities(kind: str) -> None:
    manifest = target_capability_manifest()

    assert manifest[kind]["implemented"] is True
    assert manifest[kind]["routes"] == ["rpc", "legacy_ws", "stream", "channel"]
