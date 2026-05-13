from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api_blueprint.contract import build_agent_manifest

from .generator import load_contract_graph


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class InspectionContext:
    manifest: JsonObject
    agent: JsonObject


def load_inspection_context(config_path: str | Path | None) -> InspectionContext:
    graph = load_contract_graph(config_path, command="api-gen inspect")
    manifest = graph.to_manifest()
    return InspectionContext(
        manifest=manifest,
        agent=build_agent_manifest(manifest),
    )


def inspect_routes(config_path: str | Path | None) -> JsonObject:
    context = load_inspection_context(config_path)
    routes = [
        {
            "id": route.get("id"),
            "kind": route.get("kind"),
            "methods": route.get("methods", []),
            "url": route.get("url"),
            "operation": route.get("operation"),
            "schemas": route.get("schemas", []),
            "errors": route.get("errors", []),
            "targets": sorted((route.get("artifacts") or {}).keys()),
        }
        for route in _list_of_maps(context.agent.get("routes"))
    ]
    return {"count": len(routes), "routes": routes}


def inspect_route(config_path: str | Path | None, route_query: str) -> JsonObject:
    context = load_inspection_context(config_path)
    return _inspect_route_from_context(context, route_query)


def inspect_routes_detail(config_path: str | Path | None, route_queries: Sequence[str]) -> JsonObject:
    context = load_inspection_context(config_path)
    routes = [_inspect_route_from_context(context, route_query) for route_query in route_queries]
    return {
        "count": len(routes),
        "routes": routes,
    }


def _inspect_route_from_context(context: InspectionContext, route_query: str) -> JsonObject:
    route = _find_route(context.agent, route_query)
    route_id = _string(route.get("id"))
    return {
        "id": route_id,
        "service_id": route.get("service_id"),
        "kind": route.get("kind"),
        "operation": route.get("operation"),
        "methods": route.get("methods", []),
        "url": route.get("url"),
        "request_models": route.get("request_models", []),
        "binary_schema": route.get("binary_schema"),
        "response_model": route.get("response_model"),
        "connection": route.get("connection"),
        "errors": route.get("errors", []),
        "schemas": route.get("schemas", []),
        "artifacts": route.get("artifacts", {}),
    }


def inspect_files(config_path: str | Path | None, route_query: str, target_id: str | None = None) -> JsonObject:
    route = inspect_route(config_path, route_query)
    return _inspect_files_from_route(route, target_id=target_id)


def inspect_files_many(
    config_path: str | Path | None,
    route_queries: Sequence[str],
    target_id: str | None = None,
) -> JsonObject:
    routes = inspect_routes_detail(config_path, route_queries)["routes"]
    return {
        "count": len(routes),
        "routes": [_inspect_files_from_route(route, target_id=target_id) for route in _list_of_maps(routes)],
    }


def _inspect_files_from_route(route: Mapping[str, Any], target_id: str | None = None) -> JsonObject:
    artifacts = route.get("artifacts") if isinstance(route.get("artifacts"), Mapping) else {}
    selected: dict[str, object] = {}
    for artifact_target_id, artifact in artifacts.items():
        if target_id is not None and artifact_target_id != target_id:
            continue
        selected[str(artifact_target_id)] = dict(artifact) if isinstance(artifact, Mapping) else artifact
    if target_id is not None and not selected:
        raise ValueError(f"target does not select route: {target_id} -> {route['id']}")
    return {
        "route": route["id"],
        "targets": selected,
    }


def inspect_schema(config_path: str | Path | None, schema_query: str) -> JsonObject:
    context = load_inspection_context(config_path)
    return _inspect_schema_from_context(context, schema_query)


def inspect_schemas(config_path: str | Path | None, schema_queries: Sequence[str]) -> JsonObject:
    context = load_inspection_context(config_path)
    schemas = [_inspect_schema_from_context(context, schema_query) for schema_query in schema_queries]
    return {
        "count": len(schemas),
        "schemas": schemas,
    }


def inspect_binary_schema(config_path: str | Path | None, schema_query: str) -> JsonObject:
    context = load_inspection_context(config_path)
    matches: list[JsonObject] = []
    for route in _list_of_maps(context.manifest.get("routes")):
        request = route.get("request")
        if not isinstance(request, Mapping):
            continue
        schema = request.get("binary_schema")
        if not isinstance(schema, Mapping):
            continue
        name = _string(schema.get("name"))
        source = _string(schema.get("source"))
        if schema_query in {name, source} or schema_query in name or schema_query in source:
            matches.append({"route": route.get("id"), "schema": dict(schema)})
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f"binary schema not found: {schema_query}")
    raise ValueError(
        "binary schema query matched multiple schemas: "
        + schema_query
        + " -> "
        + ", ".join(_string(item["schema"].get("name")) for item in matches)
    )


def _inspect_schema_from_context(context: InspectionContext, schema_query: str) -> JsonObject:
    schema_name = _find_schema_name(context.manifest, schema_query)
    raw_schemas = context.manifest.get("schemas")
    schemas = raw_schemas if isinstance(raw_schemas, Mapping) else {}
    schema = schemas.get(schema_name)
    if not isinstance(schema, Mapping):
        raise ValueError(f"schema not found: {schema_query}")
    return {
        "name": schema_name,
        "schema": dict(schema),
        "inbound_routes": _schema_inbound_routes(context.agent, schema_name),
    }


def inspect_errors(config_path: str | Path | None, route_query: str | None = None) -> JsonObject:
    context = load_inspection_context(config_path)
    errors = _list_of_maps(context.manifest.get("errors"))
    if route_query is None:
        return {"count": len(errors), "errors": errors}

    return _inspect_route_errors(context, errors, route_query)


def inspect_errors_many(config_path: str | Path | None, route_queries: Sequence[str]) -> JsonObject:
    context = load_inspection_context(config_path)
    errors = _list_of_maps(context.manifest.get("errors"))
    routes = [_inspect_route_errors(context, errors, route_query) for route_query in route_queries]
    return {
        "count": len(routes),
        "routes": routes,
    }


def _inspect_route_errors(context: InspectionContext, errors: list[JsonObject], route_query: str) -> JsonObject:
    route = _find_route(context.agent, route_query)
    route_error_ids = {str(error_id) for error_id in route.get("errors", []) if error_id is not None}
    selected = [error for error in errors if _string(error.get("id")) in route_error_ids]
    return {
        "route": route.get("id"),
        "count": len(selected),
        "errors": selected,
    }


def _find_route(agent: Mapping[str, Any], query: str) -> JsonObject:
    routes = _list_of_maps(agent.get("routes"))
    exact = [route for route in routes if _string(route.get("id")) == query]
    if exact:
        return exact[0]

    matches = [
        route
        for route in routes
        if query in {
            _string(route.get("url")),
            _string(route.get("operation")),
        }
        or query in _string(route.get("id"))
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f"route not found: {query}")
    raise ValueError(f"route query matched multiple routes: {query} -> {', '.join(_string(route.get('id')) for route in matches)}")


def _find_schema_name(manifest: Mapping[str, Any], query: str) -> str:
    raw_schemas = manifest.get("schemas")
    schemas = raw_schemas if isinstance(raw_schemas, Mapping) else {}
    if query in schemas:
        return query
    matches = [str(name) for name in schemas if query in str(name)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f"schema not found: {query}")
    raise ValueError(f"schema query matched multiple schemas: {query} -> {', '.join(matches)}")


def _schema_inbound_routes(agent: Mapping[str, Any], schema_name: str) -> list[str]:
    return [
        _string(route.get("id"))
        for route in _list_of_maps(agent.get("routes"))
        if schema_name in {str(name) for name in route.get("schemas", [])}
    ]


def _list_of_maps(value: object) -> list[JsonObject]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _string(value: object) -> str:
    return "" if value is None else str(value)
