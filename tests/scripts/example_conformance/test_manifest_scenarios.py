from __future__ import annotations

from .helpers import *


def test_manifest_marks_matrix_capabilities() -> None:
    clients = manifest.client_manifest()
    servers = manifest.server_manifest()

    assert clients["go"].supports_rpc is True
    assert clients["go"].supports_sse is False
    assert clients["typescript"].supports_websocket is True
    assert clients["flutter"].supports_sse is True
    assert clients["swift"].supports_rpc is True
    assert clients["swift"].supports_binary is True
    assert clients["swift"].supports_sse is True
    assert clients["swift"].supports_websocket is True
    assert clients["swift"].connection_policy == "native"
    assert clients["kotlin"].supports_rpc is True
    assert clients["kotlin"].supports_sse is True
    assert clients["kotlin"].supports_websocket is True
    assert clients["kotlin"].connection_policy == "native"
    assert clients["java"].supports_rpc is True
    assert clients["java"].supports_sse is True
    assert clients["java"].connection_policy == "unsupported-contract"
    assert clients["python"].supports_binary is True
    assert clients["python"].supports_websocket is True
    assert clients["python"].connection_policy == "unsupported-contract"

    assert servers["go"].enabled is True
    assert servers["java"].enabled is False
    assert servers["java"].supports_rpc is False
    assert servers["kotlin"].supports_sse is True
    assert servers["python"].supports_binary is True
    assert servers["python"].supports_websocket is True

def test_scenario_registry_covers_required_dsl_categories() -> None:
    coverage = scenarios.coverage_by_category()

    required = {
        "query",
        "json",
        "form",
        "binary",
        "raw",
        "xml",
        "static",
        "header",
        "scalar",
        "enum",
        "map",
        "deprecated",
        "empty-response",
        "typed-error",
        "sse",
        "websocket",
        "single-channel",
        "legacy-json",
        "naming-conflict",
        "multi-blueprint",
        "envelope",
        "no-envelope",
        "server-safety",
        "malformed-input",
        "early-close",
    }
    assert required <= set(coverage)
    assert "go" in coverage["binary"]
    assert "typescript" in coverage["websocket"]
    assert "java" in coverage["binary"]
    assert "swift" in coverage["binary"]
    assert "swift" in coverage["multipart"]
    assert "swift" in coverage["typed-error"]
    assert "swift" in coverage["sse"]
    assert "swift" in coverage["websocket"]
    assert "swift" in coverage["single-channel"]
    assert "python" in coverage["binary"]
    assert "flutter" in coverage["sse"]
    assert "kotlin" in coverage["sse"]
    assert "kotlin" in coverage["websocket"]
    assert "kotlin" in coverage["form"]
    assert coverage["legacy-json"] == {"typescript", "kotlin", "flutter", "swift", "python"}
    assert coverage["server-safety"] == {"server"}
    assert coverage["malformed-input"] == {"server"}

def test_scenario_registry_exposes_expanded_examples() -> None:
    registry = scenarios.scenario_registry()

    expected = {
        "raw",
        "xml",
        "static",
        "header",
        "scalar",
        "enum",
        "map",
        "deprecated",
        "empty-response",
        "binary-br",
        "audit-binary",
        "wide-binary",
        "single-channel",
        "legacy-json",
    }
    assert expected <= set(registry)
    assert registry["raw"].route_ids == ("api.demo.post.raw",)
    assert registry["xml"].route_ids == ("api.demo.delete.delete",)
    assert registry["static"].route_ids == ("static.static.get.docjson", "static.static.get.dochaha")
    assert registry["header"].route_ids == ("api.demo.get.abc",)
    assert registry["scalar"].route_ids == ("api.hello.get.string", "api.hello.get.uint64")
    assert registry["enum"].route_ids == ("api.hello.get.stringemun", "api.hello.get.listenum")
    assert registry["map"].route_ids == (
        "api.demo.post.mapmodel",
        "api.hello.get.abc",
        "api.hello.get.mapenum",
    )
    assert registry["deprecated"].route_ids == ("api.demo.post.postdeprecated",)
    assert registry["empty-response"].route_ids == ("api.demo.post.emptyresponse",)
    assert registry["binary-br"].route_ids == ("api.binary.post.packet",)
    assert registry["audit-binary"].route_ids == ("api.binary.post.auditpacket",)
    assert registry["wide-binary"].route_ids == ("api.binary.post.widepacket",)
    assert registry["wide-binary"].clients == ("swift",)
    assert registry["single-channel"].route_ids == ("api.api.channel.ws",)
    assert registry["legacy-json"].route_ids == (
        "legacy.account.get.profile",
        "legacy.room.get.list",
        "legacy.legacy_json.get.compat",
    )
    assert registry["legacy-json"].clients == ("typescript", "kotlin", "flutter", "swift", "python")

def test_user_visible_example_routes_have_conformance_status() -> None:
    contract = json.loads((REPO_ROOT / "examples/api-blueprint.index.json").read_text(encoding="utf-8"))
    route_ids = {route["id"] for route in contract["routes"]}
    covered_route_ids = {route_id for scenario in scenarios.scenario_registry().values() for route_id in scenario.route_ids}
    unsupported_route_ids = set(scenarios.unsupported_route_ids())

    assert route_ids <= covered_route_ids | unsupported_route_ids
    assert covered_route_ids <= route_ids

def test_expanded_scenarios_are_gated_by_server_capabilities() -> None:
    rpc_names = {
        "raw",
        "xml",
        "static",
        "header",
        "scalar",
        "enum",
        "map",
        "deprecated",
        "empty-response",
        "single-channel",
        "legacy-json",
    }
    binary_names = {"binary-br", "audit-binary", "wide-binary"}

    for name in rpc_names:
        assert scenarios.server_supports_scenario("go", scenarios.scenario_registry()[name]) is True
    for name in binary_names:
        assert scenarios.server_supports_scenario("go", scenarios.scenario_registry()[name]) is True

def test_filter_scenarios_rejects_unknown_names() -> None:
    with pytest.raises(ValueError, match="unknown conformance scenario"):
        scenarios.filter_scenarios(["missing"])
