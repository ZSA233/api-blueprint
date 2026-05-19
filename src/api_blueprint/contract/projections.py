from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from api_blueprint.writer.core.go_naming import to_go_package_path
from api_blueprint.writer.core.planning import route_matches_rule


JsonObject = dict[str, Any]

AGENT_MANIFEST_KIND = "api-blueprint.agent"
INDEX_MANIFEST_KIND = "api-blueprint.index"
SHARD_ROOT = "api-blueprint.contract.d"
AGENT_READ_ORDER_NOTE = "优先使用 `api-gen inspect` 按需查询 route/schema/files/errors；其次读取轻量 `api-blueprint.index.json` 查看接口目录；只有离线归档、diff 或需要完整快照时才读 full contract/shards，最后才看生成物"


def build_index_manifest(manifest: Mapping[str, Any]) -> JsonObject:
    services = _list_of_maps(manifest.get("services"))
    routes = _list_of_maps(manifest.get("routes"))
    schemas = _mapping_of_maps(manifest.get("schemas"))
    errors = _list_of_maps(manifest.get("errors"))
    connections = _list_of_maps(manifest.get("connections"))
    targets = _list_of_maps(manifest.get("targets"))

    return {
        "kind": INDEX_MANIFEST_KIND,
        "version": str(manifest.get("version") or "1.0"),
        "generator": dict(manifest.get("generator")) if isinstance(manifest.get("generator"), Mapping) else {},
        "counts": _counts(services, routes, schemas, errors, connections, targets),
        "purpose": "Lightweight route catalog. Use inspect commands for route schemas, errors, generated files, and full details.",
        "queries": {
            "routes": "api-gen inspect routes -c api-blueprint.toml",
            "route": "api-gen inspect route <route-id> [<route-id> ...] -c api-blueprint.toml",
            "schema": "api-gen inspect schema <SchemaName> [<SchemaName> ...] -c api-blueprint.toml",
            "errors": "api-gen inspect errors --route <route-id> [--route <route-id> ...] -c api-blueprint.toml",
            "files": "api-gen inspect files --route <route-id> [--route <route-id> ...] --target <target-id> -c api-blueprint.toml",
            "full_contract": "api-gen manifest --profile full --out api-blueprint.contract.json -c api-blueprint.toml",
        },
        "read_order": [
            {
                "step": 1,
                "path": "api-gen inspect",
                "purpose": "Query exact route, schema, error, and generated file details on demand.",
            },
            {
                "step": 2,
                "path": "api-blueprint.index.json",
                "purpose": "Lightweight offline route catalog for choosing which route to inspect next.",
            },
            {
                "step": 3,
                "path": f"{SHARD_ROOT}/index.json",
                "purpose": "Optional offline shard index when inspect is unavailable or a larger local snapshot is needed.",
            },
            {
                "step": 4,
                "path": "api-blueprint.contract.json",
                "purpose": "Explicit full fallback snapshot for diff, archiving, and exhaustive contract inspection.",
            },
            {
                "step": 5,
                "path": "generated artifacts",
                "purpose": "Read generated source only after locating the relevant target-specific files.",
            },
        ],
        "services": [_service_index_summary(service, routes) for service in services],
        "routes": [_route_index_summary(route) for route in routes],
        "targets": [_target_index_summary(target, routes) for target in targets],
        "agent_notes": [
            AGENT_READ_ORDER_NOTE,
            "This index intentionally omits route schemas, errors, and generated file lists; use the `queries` commands for those details.",
            "Do not open api-blueprint.contract.json by default; generate or read it only for diff, archiving, or exhaustive fallback.",
        ],
    }


def build_agent_manifest(manifest: Mapping[str, Any]) -> JsonObject:
    services = _list_of_maps(manifest.get("services"))
    routes = _list_of_maps(manifest.get("routes"))
    schemas = _mapping_of_maps(manifest.get("schemas"))
    errors = _list_of_maps(manifest.get("errors"))
    connections = _list_of_maps(manifest.get("connections"))
    targets = _list_of_maps(manifest.get("targets"))
    capabilities = manifest.get("capabilities") if isinstance(manifest.get("capabilities"), Mapping) else {}
    route_artifacts = _route_artifacts(routes, targets)

    return {
        "kind": AGENT_MANIFEST_KIND,
        "version": str(manifest.get("version") or "1.0"),
        "generator": dict(manifest.get("generator")) if isinstance(manifest.get("generator"), Mapping) else {},
        "source": "api-blueprint.contract.json",
        "counts": _counts(services, routes, schemas, errors, connections, targets),
        "read_order": [
            {
                "step": 1,
                "path": "api-gen inspect",
                "purpose": "Query routes, route details, schema details, errors, and generated file indexes on demand.",
            },
            {
                "step": 2,
                "path": "api-blueprint.agent.json",
                "purpose": "Compact cross-service index for routes, schemas, connections, targets, and artifacts.",
            },
            {
                "step": 3,
                "path": f"{SHARD_ROOT}/index.json",
                "purpose": "Optional shard directory index; use it when inspect is unavailable or a full offline snapshot is needed.",
            },
            {
                "step": 4,
                "path": f"{SHARD_ROOT}/routes/<route_id>.json",
                "purpose": "Optional route shard for request/response models, connection messages, and target imports.",
            },
            {
                "step": 5,
                "path": "generated artifacts",
                "purpose": "Only inspect generated source when the artifact/import index points to a target-specific entry.",
            },
        ],
        "shards": {
            "index": f"{SHARD_ROOT}/index.json",
            "routes_dir": f"{SHARD_ROOT}/routes",
            "services_dir": f"{SHARD_ROOT}/services",
            "schemas_dir": f"{SHARD_ROOT}/schemas",
        },
        "services": [_service_summary(service, routes) for service in services],
        "routes": [_route_summary(route, schemas, route_artifacts.get(_route_id(route), {})) for route in routes],
        "errors": errors,
        "connections": [_connection_summary(connection) for connection in connections],
        "targets": [_target_summary(target, routes) for target in targets],
        "capabilities": dict(capabilities),
        "agent_notes": [
            AGENT_READ_ORDER_NOTE,
            "Prefer batched `api-gen inspect route <route_id> [<route_id> ...]` and repeated `--route` for files/errors over opening generated trees.",
            "Use route shards only for offline snapshots or when inspect output is not enough.",
            "Use generated artifacts only for language-specific invocation details after locating them with inspect or artifacts.",
        ],
    }


def build_contract_shards(manifest: Mapping[str, Any]) -> dict[str, JsonObject]:
    services = _list_of_maps(manifest.get("services"))
    routes = _list_of_maps(manifest.get("routes"))
    schemas = _mapping_of_maps(manifest.get("schemas"))
    errors = _list_of_maps(manifest.get("errors"))
    targets = _list_of_maps(manifest.get("targets"))
    route_artifacts = _route_artifacts(routes, targets)
    routes_by_service = _routes_by_service(routes)

    shards: dict[str, JsonObject] = {
        "index.json": {
            "version": str(manifest.get("version") or "1.0"),
            "generator": dict(manifest.get("generator")) if isinstance(manifest.get("generator"), Mapping) else {},
            "counts": _counts(services, routes, schemas, errors, _list_of_maps(manifest.get("connections")), targets),
            "errors": errors,
            "services": [
                {
                    "id": _string(service.get("id")),
                    "shard": f"services/{_safe_file_stem(_string(service.get('id')))}.json",
                }
                for service in services
            ],
            "routes": [
                {
                    "id": _route_id(route),
                    "kind": _string(route.get("kind")),
                    "url": _string(route.get("url")),
                    "shard": f"routes/{_safe_file_stem(_route_id(route))}.json",
                }
                for route in routes
            ],
            "schemas": [
                {
                    "name": name,
                    "shard": f"schemas/{_safe_file_stem(name)}.json",
                }
                for name in sorted(schemas)
            ],
        }
    }

    for service in services:
        service_id = _string(service.get("id"))
        service_routes = routes_by_service.get(service_id, [])
        shards[f"services/{_safe_file_stem(service_id)}.json"] = {
            "service": dict(service),
            "routes": [_route_summary(route, schemas, route_artifacts.get(_route_id(route), {})) for route in service_routes],
        }

    for route in routes:
        route_id = _route_id(route)
        route_schema_names = _route_schema_names(route, schemas)
        shards[f"routes/{_safe_file_stem(route_id)}.json"] = {
            "route": dict(route),
            "service": _service_for_route(route, services),
            "connection": route.get("connection"),
            "errors": list(route.get("errors") if isinstance(route.get("errors"), list) else []),
            "schemas": {name: schemas[name] for name in route_schema_names if name in schemas},
            "artifacts": route_artifacts.get(route_id, {}),
        }

    inbound_routes = _schema_inbound_routes(routes, schemas)
    for name, schema in schemas.items():
        shards[f"schemas/{_safe_file_stem(name)}.json"] = {
            "schema": dict(schema),
            "inbound_routes": inbound_routes.get(name, []),
        }

    return shards


def render_agent_markdown(manifest: Mapping[str, Any]) -> str:
    agent = build_agent_manifest(manifest)
    lines = [
        "# api-blueprint Agent Guide",
        "",
        AGENT_READ_ORDER_NOTE + "。",
        "",
        "## Preferred Commands",
        "- `api-gen inspect routes -c api-blueprint.toml`",
        "- `api-gen inspect route <route_id> [<route_id> ...] -c api-blueprint.toml`",
        "- `api-gen inspect files --route <route_id> [--route <route_id> ...] --target <target_id> -c api-blueprint.toml`",
        "- `api-gen inspect schema <SchemaName> [<SchemaName> ...] -c api-blueprint.toml`",
        "- `api-gen inspect errors --route <route_id> [--route <route_id> ...] -c api-blueprint.toml`",
        "",
        "## Read Order",
    ]
    for item in agent["read_order"]:
        lines.append(f"{item['step']}. `{item['path']}` - {item['purpose']}")
    lines.extend(["", "## Counts"])
    for key, value in agent["counts"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Routes"])
    for route in agent["routes"]:
        lines.append(f"- `{route['id']}` `{route['kind']}` `{route['url']}` -> `{route['shard']}`")
    lines.extend(
        [
            "",
            "## Generated Artifacts",
            "Use route `artifacts` entries for import paths and generated files. Do not start by reading generated source.",
            "",
        ]
    )
    return "\n".join(lines)


def _counts(
    services: list[JsonObject],
    routes: list[JsonObject],
    schemas: Mapping[str, JsonObject],
    errors: list[JsonObject],
    connections: list[JsonObject],
    targets: list[JsonObject],
) -> JsonObject:
    return {
        "services": len(services),
        "routes": len(routes),
        "schemas": len(schemas),
        "errors": len(errors),
        "connections": len(connections),
        "targets": len(targets),
    }


def _service_summary(service: Mapping[str, Any], routes: list[JsonObject]) -> JsonObject:
    service_id = _string(service.get("id"))
    route_ids = [_route_id(route) for route in routes if _string(route.get("service_id")) == service_id]
    return {
        "id": service_id,
        "root": _string(service.get("root")),
        "group": _string(service.get("group")),
        "name": _string(service.get("name")),
        "path": _string(service.get("path")),
        "route_count": len(route_ids),
        "routes": route_ids,
        "shard": f"{SHARD_ROOT}/services/{_safe_file_stem(service_id)}.json",
    }


def _route_summary(route: Mapping[str, Any], schemas: Mapping[str, JsonObject], artifacts: Mapping[str, Any]) -> JsonObject:
    route_id = _route_id(route)
    response = route.get("response") if isinstance(route.get("response"), Mapping) else {}
    return {
        "id": route_id,
        "service_id": _string(route.get("service_id")),
        "kind": _string(route.get("kind")),
        "operation": _string(route.get("operation")),
        "methods": list(route.get("methods") if isinstance(route.get("methods"), list) else []),
        "url": _string(route.get("url")),
        "request_models": _request_models(route),
        "binary_schema": _binary_schema_name(route),
        "response_model": response.get("model") if isinstance(response, Mapping) else None,
        "connection": _compact_connection(route.get("connection")),
        "errors": list(route.get("errors") if isinstance(route.get("errors"), list) else []),
        "schemas": _route_schema_names(route, schemas),
        "artifacts": dict(artifacts),
        "hash": _string(route.get("hash")),
        "shard": f"{SHARD_ROOT}/routes/{_safe_file_stem(route_id)}.json",
    }


def _service_index_summary(service: Mapping[str, Any], routes: list[JsonObject]) -> JsonObject:
    service_id = _string(service.get("id"))
    route_count = len([route for route in routes if _string(route.get("service_id")) == service_id])
    return {
        "id": service_id,
        "root": _string(service.get("root")),
        "group": _string(service.get("group")),
        "name": _string(service.get("name")),
        "path": _string(service.get("path")),
        "route_count": route_count,
    }


def _route_index_summary(route: Mapping[str, Any]) -> JsonObject:
    return {
        "id": _route_id(route),
        "service_id": _string(route.get("service_id")),
        "kind": _string(route.get("kind")),
        "operation": _string(route.get("operation")),
        "methods": list(route.get("methods") if isinstance(route.get("methods"), list) else []),
        "url": _string(route.get("url")),
    }


def _connection_summary(connection: Mapping[str, Any]) -> JsonObject:
    route_id = _string(connection.get("route_id"))
    return {
        "route_id": route_id,
        "kind": _string(connection.get("kind")),
        "delivery": _string(connection.get("delivery")),
        "scope": _string(connection.get("scope")),
        "open_model": connection.get("open_model"),
        "close_model": connection.get("close_model"),
        "server_message_models": _message_models(connection.get("server_message")),
        "client_message_models": _message_models(connection.get("client_message")),
        "shard": f"{SHARD_ROOT}/routes/{_safe_file_stem(route_id)}.json",
    }


def _target_index_summary(target: Mapping[str, Any], routes: list[JsonObject]) -> JsonObject:
    selected_routes = [
        _route_id(route)
        for route in routes
        if _string(target.get("id")) and _target_selects_route(target, route)
    ]
    return {
        "id": _string(target.get("id")),
        "kind": _string(target.get("kind")),
        "out_dir": target.get("out_dir"),
        "role": _target_role(target),
        "route_count": len(selected_routes),
    }


def _target_summary(target: Mapping[str, Any], routes: list[JsonObject]) -> JsonObject:
    return {
        "id": _string(target.get("id")),
        "kind": _string(target.get("kind")),
        "out_dir": target.get("out_dir"),
        "role": _target_role(target),
        "artifacts": _target_level_artifacts(target, routes),
    }


def _target_role(target: Mapping[str, Any]) -> str:
    kind = _string(target.get("kind"))
    if kind.endswith("-server"):
        return "server"
    if kind.endswith("-client"):
        return "client"
    if kind.endswith("-transport"):
        return "transport"
    if kind.startswith("grpc-"):
        return "grpc"
    return kind or "unknown"


def _target_level_artifacts(target: Mapping[str, Any], routes: list[JsonObject]) -> JsonObject:
    route_ids = [_route_id(route) for route in routes]
    return {
        "route_count": len(route_ids),
        "routes": route_ids,
    }


def _route_artifacts(routes: list[JsonObject], targets: list[JsonObject]) -> dict[str, JsonObject]:
    result: dict[str, JsonObject] = {}
    targets_by_id = {_string(target.get("id")): target for target in targets if _string(target.get("id"))}
    for route in routes:
        route_id = _route_id(route)
        result[route_id] = {}
        for target in targets:
            target_id = _string(target.get("id"))
            if not target_id:
                continue
            if not _target_selects_route(target, route):
                continue
            artifact = _artifact_for_route(target, route, targets_by_id)
            if artifact:
                result[route_id][target_id] = artifact
    return result


def _artifact_for_route(
    target: Mapping[str, Any],
    route: Mapping[str, Any],
    targets_by_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> JsonObject:
    kind = _string(target.get("kind"))
    out_dir = _string(target.get("out_dir"))
    service_id = _string(route.get("service_id"))
    root, group = _split_service_id(service_id)
    route_path = _route_path(root, group)
    go_root_segment = to_go_package_path(root, fallback="root")
    go_group_segment = to_go_package_path(group, fallback=go_root_segment)
    go_route_path = _route_path(go_root_segment, go_group_segment)
    python_route_package = route_path.replace("/", ".")
    kotlin_route_package = route_path.replace("/", ".")
    pascal_group = _pascal(group)
    has_binary_schema = _binary_schema_name(route) is not None
    files: list[str] = []
    imports: list[str] = []
    handled = True

    if kind == "go-server":
        base = _join(out_dir, "routes", go_route_path)
        files = [_join(base, "gen_interface.go"), _join(base, "gen_types.go")]
        if has_binary_schema:
            files.append(_join(base, "_gen_binary", "gen_binary.go"))
        import_root = _string(target.get("go_import_root")) or _string(target.get("module"))
        if import_root:
            imports = [_join(import_root, "routes", go_route_path)]
    elif kind == "go-client":
        base = _join(out_dir, "routes", go_route_path)
        transport_base = _join(out_dir, "transports", "http")
        files = [
            _join(base, "gen_types.go"),
            _join(base, "gen_client.go"),
            _join(base, "client.go"),
            _join(transport_base, "gen_transport.go"),
            _join(transport_base, "client.go"),
        ]
        if has_binary_schema:
            files.append(_join(base, "gen_binary.go"))
        module = _string(target.get("go_import_root")) or _string(target.get("module"))
        if module:
            imports = [_join(module, "routes", go_route_path)]
    elif kind == "typescript-client":
        base = _join(out_dir, root, "routes", root, "" if root == group else group)
        files = [_join(base, "client.ts"), _join(base, "types.ts")]
        if has_binary_schema:
            files.append(_join(base, "gen_binary.ts"))
        imports = [_posix_without_suffix(base)]
    elif kind == "kotlin-client":
        package = _string(target.get("package"))
        package_path = package.replace(".", "/")
        base = _join(out_dir, package_path, root, "routes", route_path)
        files = [
            _join(base, f"{pascal_group}Types.kt"),
            _join(base, f"Gen{pascal_group}Api.kt"),
            _join(base, f"{pascal_group}Api.kt"),
        ]
        if package:
            imports = [f"{package}.{root}.routes.{kotlin_route_package}.{pascal_group}Api"]
    elif kind == "java-client":
        package = _string(target.get("package"))
        package_path = package.replace(".", "/")
        base = _join(out_dir, package_path, root, "routes", route_path)
        transport_base = _join(out_dir, package_path, root, "transports", "http")
        files = [
            _join(base, f"{pascal_group}Types.java"),
            _join(base, f"Gen{pascal_group}Api.java"),
            _join(base, f"{pascal_group}Api.java"),
            _join(transport_base, "GenJdkHttpApiTransport.java"),
            _join(transport_base, "HttpApiClient.java"),
        ]
        if package:
            imports = [f"{package}.{root}.routes.{kotlin_route_package}.{pascal_group}Api"]
    elif kind == "python-client":
        package_root = _string(target.get("python_package_root")) or "api_blueprint_generated"
        package_parts = _python_package_parts(package_root)
        base = _join(out_dir, *package_parts, root, "routes", route_path)
        transport_base = _join(out_dir, *package_parts, root, "transports", "http")
        files = [
            _join(base, "gen_client.py"),
            _join(base, "gen_types.py"),
            _join(base, "client.py"),
            _join(transport_base, "gen_client.py"),
        ]
        if has_binary_schema:
            files.append(_join(base, "gen_binary.py"))
        imports = [f"{package_root}.{root}.routes.{python_route_package}.client"]
    elif kind == "python-server":
        package_root = _string(target.get("python_package_root")) or "api_blueprint_generated"
        package_parts = _python_package_parts(package_root)
        route_base = _join(out_dir, *package_parts, root, "routes", route_path)
        transport_base = _join(out_dir, *package_parts, root, "transports", "http")
        files = [
            _join(route_base, "gen_service.py"),
            _join(route_base, "service.py"),
            _join(transport_base, "gen_server.py"),
            _join(transport_base, "server.py"),
        ]
        if has_binary_schema:
            files.append(_join(route_base, "gen_binary.py"))
        imports = [
            f"{package_root}.{root}.routes.{python_route_package}.service",
            f"{package_root}.{root}.transports.http.server",
        ]
    elif kind == "java-server":
        package = _string(target.get("package"))
        package_path = package.replace(".", "/")
        route_base = _join(out_dir, package_path, root, "routes", route_path)
        transport_base = _join(out_dir, package_path, root, "transports", "http")
        files = [
            _join(route_base, f"Gen{pascal_group}Service.java"),
            _join(route_base, f"{pascal_group}Types.java"),
            _join(route_base, f"{pascal_group}ServiceStub.java"),
            _join(route_base, f"{pascal_group}Service.java"),
            _join(transport_base, route_path, f"Gen{pascal_group}Controller.java"),
        ]
        if package:
            imports = [
                f"{package}.{root}.routes.{kotlin_route_package}.{pascal_group}Service",
                f"{package}.{root}.transports.http.{kotlin_route_package}.Gen{pascal_group}Controller",
            ]
    elif kind == "wails-transport":
        overlay = _string(target.get("overlay_name")) or "wails"
        server_target = (
            targets_by_id.get(_string(target.get("server"))) if targets_by_id is not None else None
        )
        client_ids = list(target.get("clients") if isinstance(target.get("clients"), list) else [])
        client_target = (
            targets_by_id.get(_string(client_ids[0])) if targets_by_id is not None and client_ids else None
        )
        go_out_dir = _string(server_target.get("out_dir")) if server_target is not None else "golang"
        ts_out_dir = _string(client_target.get("out_dir")) if client_target is not None else "typescript"
        files = [
            _join(go_out_dir, "transports", overlay, go_route_path, "gen_service.go"),
            _join(ts_out_dir, root, "transports", overlay, root, "" if root == group else group, "client.ts"),
        ]
    elif kind == "grpc-proto":
        files = [_join(out_dir, root, f"{group}.proto")]
    elif kind == "grpc-go":
        module = _string(target.get("module"))
        package_path = _join(root, group)
        files = [
            _join(out_dir, package_path, f"{group}.pb.go"),
            _join(out_dir, package_path, f"{group}_grpc.pb.go"),
        ]
        if module:
            imports = [_join(module, package_path)]
    elif kind == "grpc-python":
        package_root = _string(target.get("python_package_root"))
        import_prefix = f"{package_root}." if package_root else ""
        files = [
            _join(out_dir, *(package_root.split(".") if package_root else ()), root, f"{group}_pb2.py"),
            _join(out_dir, *(package_root.split(".") if package_root else ()), root, f"{group}_pb2_grpc.py"),
        ]
        imports = [f"{import_prefix}{root}.{group}_pb2", f"{import_prefix}{root}.{group}_pb2_grpc"]
    else:
        handled = False

    if not handled:
        return {}
    return {"kind": kind, "files": [path for path in files if path], "imports": imports}


def _target_selects_route(target: Mapping[str, Any], route: Mapping[str, Any]) -> bool:
    include = [str(item) for item in target.get("include", [])] if isinstance(target.get("include"), list) else []
    exclude = [str(item) for item in target.get("exclude", [])] if isinstance(target.get("exclude"), list) else []
    if include and not any(route_matches_rule(route, rule) for rule in include):
        return False
    return not any(route_matches_rule(route, rule) for rule in exclude)


def _route_schema_names(route: Mapping[str, Any], schemas: Mapping[str, JsonObject]) -> list[str]:
    direct = set(_request_models(route))
    response = route.get("response")
    if isinstance(response, Mapping) and response.get("model") is not None:
        direct.add(str(response["model"]))
    connection = route.get("connection")
    if isinstance(connection, Mapping):
        for key in ("open_model", "close_model"):
            if connection.get(key) is not None:
                direct.add(str(connection[key]))
        for message_key in ("server_message", "client_message"):
            direct.update(_message_models(connection.get(message_key)))

    result: set[str] = set()
    pending = list(direct)
    while pending:
        name = pending.pop()
        if name in result or name not in schemas:
            continue
        result.add(name)
        for ref in _collect_schema_refs(schemas[name]):
            if ref not in result:
                pending.append(ref)
    return sorted(result)


def _request_models(route: Mapping[str, Any]) -> list[str]:
    request = route.get("request")
    if not isinstance(request, Mapping):
        return []
    models = []
    for key in ("query_model", "json_model", "form_model", "binary_model"):
        value = request.get(key)
        if value is not None:
            models.append(str(value))
    return models


def _binary_schema_name(route: Mapping[str, Any]) -> str | None:
    request = route.get("request")
    if not isinstance(request, Mapping):
        return None
    schema = request.get("binary_schema")
    if not isinstance(schema, Mapping):
        return None
    name = schema.get("name")
    return str(name) if name is not None else None


def _message_models(message: object) -> list[str]:
    if not isinstance(message, Mapping):
        return []
    return [str(variant["model"]) for variant in _list_of_maps(message.get("variants")) if variant.get("model") is not None]


def _compact_connection(connection: object) -> JsonObject | None:
    if not isinstance(connection, Mapping):
        return None
    return {
        "kind": _string(connection.get("kind")),
        "delivery": _string(connection.get("delivery")),
        "scope": _string(connection.get("scope")),
        "open_model": connection.get("open_model"),
        "close_model": connection.get("close_model"),
        "server_message_models": _message_models(connection.get("server_message")),
        "client_message_models": _message_models(connection.get("client_message")),
    }


def _collect_schema_refs(value: object) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, Mapping):
        ref = value.get("ref")
        if isinstance(ref, str):
            refs.add(ref)
        for child in value.values():
            refs.update(_collect_schema_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.update(_collect_schema_refs(child))
    return refs


def _schema_inbound_routes(routes: list[JsonObject], schemas: Mapping[str, JsonObject]) -> dict[str, list[str]]:
    inbound: dict[str, list[str]] = {name: [] for name in schemas}
    for route in routes:
        route_id = _route_id(route)
        for name in _route_schema_names(route, schemas):
            inbound.setdefault(name, []).append(route_id)
    return inbound


def _routes_by_service(routes: list[JsonObject]) -> dict[str, list[JsonObject]]:
    result: dict[str, list[JsonObject]] = {}
    for route in routes:
        result.setdefault(_string(route.get("service_id")), []).append(route)
    return result


def _service_for_route(route: Mapping[str, Any], services: list[JsonObject]) -> JsonObject | None:
    service_id = _string(route.get("service_id"))
    for service in services:
        if _string(service.get("id")) == service_id:
            return dict(service)
    return None


def _split_service_id(service_id: str) -> tuple[str, str]:
    if "." not in service_id:
        return service_id or "root", service_id or "root"
    root, group = service_id.split(".", 1)
    return root or "root", group or root or "root"


def _route_path(root: str, group: str) -> str:
    return root if root == group else _join(root, group)


def _python_package_parts(package_root: str) -> tuple[str, ...]:
    return tuple(part for part in re.split(r"[./]+", package_root) if part)


def _route_id(route: Mapping[str, Any]) -> str:
    return _string(route.get("id"))


def _safe_file_stem(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return safe or "root"


def _pascal(value: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in re.split(r"[^A-Za-z0-9]+", value) if part)


def _join(*parts: object) -> str:
    normalized = [str(part).strip("/") for part in parts if str(part).strip("/")]
    return "/".join(normalized)


def _posix_without_suffix(path: str) -> str:
    return path.removesuffix(".ts").removesuffix(".go").removesuffix(".kt")


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""


def _list_of_maps(value: object) -> list[JsonObject]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _mapping_of_maps(value: object) -> dict[str, JsonObject]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): dict(item) for key, item in value.items() if isinstance(item, Mapping)}
