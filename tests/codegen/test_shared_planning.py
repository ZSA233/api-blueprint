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
from api_blueprint.writer.core.sdk_names import RoutePublicNames, go_exported_field_name


class Event(Model):
    value = String(description="value")


def test_route_public_names_use_operation_id_and_route_local_suffixes() -> None:
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.PUT("/1put", operation_id="putDemo").RSP()

    route = build_contract_graph([bp]).to_manifest()["routes"][0]
    names = RoutePublicNames.from_operation(route["operation"])

    assert names.operation == "PutDemo"
    assert names.query == "PutDemoQuery"
    assert names.json == "PutDemoJSON"
    assert names.form == "PutDemoForm"
    assert names.headers == "PutDemoHeaders"
    assert names.response == "PutDemoResponse"


def test_go_public_field_names_preserve_common_initialisms() -> None:
    assert go_exported_field_name("anon_kv") == "AnonKV"
    assert go_exported_field_name("item_ids") == "ItemIDs"
    assert go_exported_field_name("api_url") == "APIURL"


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


@pytest.mark.parametrize("kind", ["kotlin-client", "kotlin-server"])
def test_kotlin_capability_accepts_connection_routes(kind: str) -> None:
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.STREAM("/events").SERVER_MESSAGE(Event)
        views.CHANNEL("/chat").SERVER_MESSAGE(Event).CLIENT_MESSAGE(Event)

    graph = build_contract_graph([bp])
    target = ResolvedApiTargetConfig(id=kind, kind=kind, out_dir=None, package="com.example")

    assert capability_errors(graph, (target,)) == []


@pytest.mark.parametrize(
    ("kind", "target_kwargs"),
    [
        ("go-client", {"module": "example.com/client"}),
        ("typescript-client", {}),
        ("kotlin-client", {"package": "com.example"}),
        ("kotlin-server", {"package": "com.example"}),
        ("java-client", {"package": "com.example"}),
        ("python-client", {}),
    ],
)
def test_client_capabilities_accept_binary_schema_rpc_routes(kind: str, target_kwargs: dict[str, object]) -> None:
    class FakeGraph:
        def to_manifest(self) -> dict[str, object]:
            return {
                "routes": [
                    {
                        "id": "api.binary.post.packet",
                        "service_id": "api.binary",
                        "kind": "rpc",
                        "operation": "Packet",
                        "methods": ["POST"],
                        "url": "/api/binary/packet",
                        "request": {"query_model": "Query", "binary_schema": {"name": "DemoPacket"}},
                        "response": {
                            "envelope": {
                                "name": "CodeMessageDataEnvelope",
                                "kind": "code_message_data",
                                "error_identity": "nested",
                            }
                        },
                    }
                ]
            }

    target = ResolvedApiTargetConfig(id=kind, kind=kind, out_dir=None, **target_kwargs)

    assert capability_errors(FakeGraph(), (target,)) == []


def test_capability_validation_checks_only_declared_dimensions() -> None:
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.CHANNEL("/chat").SERVER_MESSAGE(Event).CLIENT_MESSAGE(Event)

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
                        "response": {
                            "envelope": {
                                "name": "NoEnvelope",
                                "kind": "none",
                                "error_identity": "none",
                            }
                        },
                    }
                ]
            }

    assert capability_errors(FakeGraph(), (target,)) == [
        "grpc-proto does not support future route: api.demo.future.route"
    ]


def test_grpc_proto_capability_declares_connection_routes_without_legacy_ws() -> None:
    manifest = target_capability_manifest()

    assert manifest["grpc-proto"]["routes"] == ["rpc", "stream", "channel"]
    assert "ignored_routes" not in manifest["grpc-proto"]


@pytest.mark.parametrize("kind", ["python-client", "python-server"])
def test_python_targets_are_real_generation_capabilities(kind: str) -> None:
    manifest = target_capability_manifest()

    assert manifest[kind]["implemented"] is True
    assert manifest[kind]["routes"] == ["rpc", "stream", "channel"]
    if kind == "python-client":
        assert "binary-schema" in manifest[kind]["requests"]


@pytest.mark.parametrize("kind", ["java-client", "java-server"])
def test_java_targets_are_real_generation_capabilities(kind: str) -> None:
    manifest = target_capability_manifest()

    assert manifest[kind]["implemented"] is True
    assert manifest[kind]["routes"] == ["rpc", "stream", "channel"]
    assert "binary-schema" in manifest[kind]["requests"]


def test_kotlin_server_is_real_generation_capability() -> None:
    manifest = target_capability_manifest()

    assert manifest["kotlin-server"]["implemented"] is True
    assert manifest["kotlin-server"]["routes"] == ["rpc", "stream", "channel"]
    assert "binary-schema" in manifest["kotlin-server"]["requests"]
