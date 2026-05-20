from __future__ import annotations

from dataclasses import dataclass

from scripts.example_conformance.manifest import client_manifest, parse_csv_filter


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
            categories=("query", "json", "raw", "xml", "envelope"),
            clients=("go", "typescript", "kotlin", "flutter"),
            route_ids=("api.demo.get.abc", "api.demo.post.testpost", "api.demo.delete.delete"),
            description="query/json/raw/xml RPC calls",
        ),
        "form": Scenario(
            name="form",
            categories=("form", "envelope"),
            clients=("go", "typescript", "kotlin", "flutter"),
            route_ids=("api.demo.post.formsubmit",),
            description="application form body calls",
        ),
        "binary": Scenario(
            name="binary",
            categories=("binary",),
            clients=("go", "typescript", "kotlin", "flutter"),
            route_ids=("api.binary.post.packet",),
            description="binary schema body calls",
        ),
        "error": Scenario(
            name="error",
            categories=("typed-error", "envelope"),
            clients=("go", "typescript", "kotlin", "flutter"),
            route_ids=("api.demo.get.errordemo",),
            description="declared, route-local, and unknown typed errors",
        ),
        "sse": Scenario(
            name="sse",
            categories=("sse",),
            clients=("typescript", "flutter"),
            route_ids=("api.demo.stream.sweepevents",),
            description="HTTP server-sent event stream",
        ),
        "websocket": Scenario(
            name="websocket",
            categories=("websocket",),
            clients=("typescript", "flutter"),
            route_ids=("api.demo.channel.assistantsession",),
            description="HTTP WebSocket channel",
        ),
        "naming": Scenario(
            name="naming",
            categories=("naming-conflict", "multi-blueprint"),
            clients=("go", "typescript", "kotlin", "flutter"),
            route_ids=("api.conflict.get.default", "alt.conflict.get.default"),
            description="reserved names, same model names, and multi-blueprint roots",
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


def scenario_names_from_cli(raw: str | None) -> tuple[str, ...]:
    return parse_csv_filter(raw, set(scenario_registry()), label="conformance scenario")


def runnable_scenarios_for_client(client: str, selected: tuple[Scenario, ...]) -> tuple[Scenario, ...]:
    clients = client_manifest()
    if client not in clients:
        raise ValueError(f"unknown conformance client: {client}")
    return tuple(scenario for scenario in selected if client in scenario.clients)

