from __future__ import annotations

from dataclasses import dataclass

from scripts.example_conformance import manifest
from scripts.example_conformance.manifest import parse_csv_filter


@dataclass(frozen=True)
class Scenario:
    name: str
    categories: tuple[str, ...]
    clients: tuple[str, ...]
    route_ids: tuple[str, ...]
    description: str


def scenario_registry() -> dict[str, Scenario]:
    return {
        "rpc": Scenario(
            name="rpc",
            categories=("query", "json", "envelope"),
            clients=("go", "typescript", "kotlin", "flutter", "java", "python"),
            route_ids=("api.demo.post.testpost", "api.demo.put.z1put"),
            description="query/json RPC calls",
        ),
        "raw": Scenario(
            name="raw",
            categories=("raw", "envelope"),
            clients=("go", "typescript", "kotlin", "flutter", "java", "python"),
            route_ids=("api.demo.post.raw",),
            description="HTTP raw response JSON payloads",
        ),
        "xml": Scenario(
            name="xml",
            categories=("xml", "envelope"),
            clients=("go", "typescript", "kotlin", "flutter", "java", "python"),
            route_ids=("api.demo.delete.delete",),
            description="XML response decoding",
        ),
        "static": Scenario(
            name="static",
            categories=("static", "no-envelope"),
            clients=("go", "typescript", "kotlin", "flutter", "java", "python"),
            route_ids=("static.static.get.docjson", "static.static.get.dochaha"),
            description="static root routes with no response envelope",
        ),
        "header": Scenario(
            name="header",
            categories=("header", "query", "envelope"),
            clients=("go", "typescript", "kotlin", "flutter", "java", "python"),
            route_ids=("api.demo.get.abc",),
            description="required x-token header handling",
        ),
        "scalar": Scenario(
            name="scalar",
            categories=("scalar", "envelope"),
            clients=("go", "typescript", "kotlin", "flutter", "java", "python"),
            route_ids=("api.hello.get.string", "api.hello.get.uint64"),
            description="scalar response bodies",
        ),
        "enum": Scenario(
            name="enum",
            categories=("enum", "envelope"),
            clients=("go", "typescript", "kotlin", "flutter", "java", "python"),
            route_ids=("api.hello.get.stringemun", "api.hello.get.listenum"),
            description="enum response bodies",
        ),
        "map": Scenario(
            name="map",
            categories=("map", "enum", "envelope"),
            clients=("go", "typescript", "kotlin", "flutter", "java", "python"),
            route_ids=("api.demo.post.mapmodel", "api.hello.get.abc", "api.hello.get.mapenum"),
            description="map and enum-key map response bodies",
        ),
        "deprecated": Scenario(
            name="deprecated",
            categories=("deprecated", "json", "envelope"),
            clients=("go", "typescript", "kotlin", "flutter", "java", "python"),
            route_ids=("api.demo.post.postdeprecated",),
            description="deprecated route remains callable",
        ),
        "form": Scenario(
            name="form",
            categories=("form", "envelope"),
            clients=("go", "typescript", "kotlin", "flutter", "java", "python"),
            route_ids=("api.demo.post.formsubmit",),
            description="application form body calls",
        ),
        "binary": Scenario(
            name="binary",
            categories=("binary",),
            clients=("go", "typescript", "kotlin", "flutter", "java", "python"),
            route_ids=("api.binary.post.packet",),
            description="binary schema body calls",
        ),
        "audit-binary": Scenario(
            name="audit-binary",
            categories=("binary",),
            clients=("go", "typescript", "kotlin", "flutter", "java", "python"),
            route_ids=("api.binary.post.auditpacket",),
            description="second binary schema body calls",
        ),
        "binary-response": Scenario(
            name="binary-response",
            categories=("binary", "raw-response"),
            clients=("go", "typescript", "kotlin", "flutter", "java", "python"),
            route_ids=("api.binary.get.auditpacketresponse",),
            description="binary schema typed response calls",
        ),
        "media": Scenario(
            name="media",
            categories=("multipart", "raw-response", "stream"),
            clients=("go", "typescript", "kotlin", "flutter", "java", "python"),
            route_ids=(
                "api.media.post.preview",
                "api.media.get.frame",
                "api.media.get.download",
                "api.media.get.downloaddynamic",
                "api.media.get.mjpeg",
            ),
            description="multipart upload and raw bytes/file/byte stream responses",
        ),
        "error": Scenario(
            name="error",
            categories=("typed-error", "envelope"),
            clients=("go", "typescript", "kotlin", "flutter", "java", "python"),
            route_ids=("api.demo.get.errordemo",),
            description="declared, route-local, and unknown typed errors",
        ),
        "sse": Scenario(
            name="sse",
            categories=("sse",),
            clients=("typescript", "kotlin", "flutter", "java", "python"),
            route_ids=("api.demo.stream.sweepevents",),
            description="HTTP server-sent event stream",
        ),
        "websocket": Scenario(
            name="websocket",
            categories=("websocket",),
            clients=("typescript", "kotlin", "flutter", "java", "python"),
            route_ids=("api.demo.channel.assistantsession",),
            description="HTTP WebSocket channel",
        ),
        "single-channel": Scenario(
            name="single-channel",
            categories=("websocket", "single-channel"),
            clients=("typescript", "kotlin", "flutter", "java", "python"),
            route_ids=("api.api.channel.ws",),
            description="/api/ws single model HTTP WebSocket channel",
        ),
        "naming": Scenario(
            name="naming",
            categories=("naming-conflict", "multi-blueprint"),
            clients=("go", "typescript", "kotlin", "flutter", "java", "python"),
            route_ids=("api.conflict.get.default", "alt.conflict.get.default"),
            description="reserved names, same model names, and multi-blueprint roots",
        ),
        "bad-json": Scenario(
            name="bad-json",
            categories=("server-safety", "malformed-input", "json"),
            clients=("server",),
            route_ids=("api.demo.post.testpost",),
            description="malformed JSON request body returns a stable non-5xx response",
        ),
        "bad-query": Scenario(
            name="bad-query",
            categories=("server-safety", "malformed-input", "query"),
            clients=("server",),
            route_ids=("api.hello.get.helloway",),
            description="malformed query value returns a stable non-5xx response",
        ),
        "malformed-websocket": Scenario(
            name="malformed-websocket",
            categories=("server-safety", "malformed-input", "websocket"),
            clients=("server",),
            route_ids=("api.demo.channel.assistantsession",),
            description="malformed WebSocket frame closes without hanging server tasks",
        ),
        "ws-early-close": Scenario(
            name="ws-early-close",
            categories=("server-safety", "early-close", "websocket"),
            clients=("server",),
            route_ids=("api.demo.channel.assistantsession",),
            description="client close during channel receive does not hang the server",
        ),
        "bad-binary": Scenario(
            name="bad-binary",
            categories=("server-safety", "malformed-input", "binary"),
            clients=("server",),
            route_ids=("api.binary.post.packet",),
            description="malformed binary request does not terminate the server process",
        ),
    }


def filter_scenarios(raw_names: tuple[str, ...] | list[str] | None = None) -> tuple[Scenario, ...]:
    registry = scenario_registry()
    if not raw_names:
        return tuple(registry.values())
    names: list[str] = []
    for raw in raw_names:
        names.extend(item.strip() for item in raw.split(",") if item.strip())
    unknown = [name for name in names if name not in registry]
    if unknown:
        raise ValueError(f"unknown conformance scenario: {', '.join(unknown)}")
    return tuple(registry[name] for name in names)


def coverage_by_category() -> dict[str, set[str]]:
    coverage: dict[str, set[str]] = {}
    for scenario in scenario_registry().values():
        for category in scenario.categories:
            coverage.setdefault(category, set()).update(scenario.clients)
    return coverage


def unsupported_route_ids() -> tuple[str, ...]:
    return ()


def scenario_names_from_cli(raw: str | None) -> tuple[str, ...]:
    return parse_csv_filter(raw, set(scenario_registry()), label="conformance scenario")


def runnable_scenarios_for_client(client: str, selected: tuple[Scenario, ...]) -> tuple[Scenario, ...]:
    clients = manifest.client_manifest()
    if client not in clients:
        raise ValueError(f"unknown conformance client: {client}")
    return tuple(scenario for scenario in selected if client in scenario.clients)


def server_safety_scenarios(selected: tuple[Scenario, ...]) -> tuple[Scenario, ...]:
    return tuple(scenario for scenario in selected if scenario.clients == ("server",))


def server_supports_scenario(server: str, scenario: Scenario) -> bool:
    servers = manifest.server_manifest()
    if server not in servers:
        raise ValueError(f"unknown conformance server: {server}")
    capability = servers[server]
    if scenario.name == "rpc":
        return capability.supports_rpc
    if scenario.name in {
        "raw",
        "xml",
        "static",
        "header",
        "scalar",
        "enum",
        "map",
        "deprecated",
    }:
        return capability.supports_rpc
    if scenario.name == "form":
        return capability.supports_form
    if scenario.name in {"binary", "audit-binary", "binary-response"}:
        return capability.supports_binary
    if scenario.name == "media":
        return capability.supports_media
    if scenario.name == "error":
        return capability.supports_typed_error
    if scenario.name == "sse":
        return capability.supports_sse
    if scenario.name in {"websocket", "single-channel"}:
        return capability.supports_websocket
    if scenario.name == "naming":
        return capability.supports_naming
    if scenario.name in {"bad-json", "bad-query"}:
        return capability.supports_rpc
    if scenario.name == "bad-binary":
        return capability.supports_binary
    if scenario.name in {"malformed-websocket", "ws-early-close"}:
        return capability.supports_websocket
    return True
