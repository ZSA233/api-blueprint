from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Sequence

from api_blueprint.application.project import build_entrypoints, load_project
from api_blueprint.config import ResolvedApiTargetConfig, ResolvedTargetConfig, resolve_config
from api_blueprint.config.resolved import ResolvedWailsConfig, ResolvedWailsTargetConfig
from api_blueprint.contract import ContractGraph, build_contract_graph, diff_manifests
from api_blueprint.engine import Blueprint


TARGET_CAPABILITY_REGISTRY: dict[str, dict[str, object]] = {
    "contract": {
        "implemented": True,
        "routes": [],
        "outputs": ["json", "markdown"],
    },
    "go-server": {
        "implemented": True,
        "routes": ["rpc", "stream", "channel"],
        "requests": ["query", "json", "form", "binary"],
        "wrappers": ["none", "general", "custom"],
    },
    "go-client": {
        "implemented": False,
        "routes": [],
        "reserved": True,
    },
    "typescript-client": {
        "implemented": True,
        "routes": ["rpc", "stream", "channel"],
        "requests": ["query", "json", "form", "binary"],
        "transport": "injected",
        "wrappers": ["none", "general", "custom"],
    },
    "kotlin-client": {
        "implemented": True,
        "routes": ["rpc"],
        "requests": ["query", "json"],
        "wrappers": ["none", "general"],
    },
    "python-server": {
        "implemented": False,
        "routes": [],
        "reserved": True,
    },
    "python-client": {
        "implemented": False,
        "routes": [],
        "reserved": True,
    },
    "http-transport": {
        "implemented": True,
        "routes": ["rpc", "stream", "channel"],
    },
    "wails-transport": {
        "implemented": True,
        "routes": ["rpc", "stream", "channel"],
        "frontend_modes": ["external", "none"],
    },
    "grpc-proto": {
        "implemented": True,
        "routes": ["rpc", "stream", "channel"],
        "outputs": ["proto"],
    },
}


def list_targets(config_path: str | Path | None) -> tuple[ResolvedApiTargetConfig, ...]:
    return resolve_config(config_path).targets


def explain_target(config_path: str | Path | None, target_id: str) -> ResolvedApiTargetConfig:
    return require_target(resolve_config(config_path).targets, target_id)


def load_contract_graph(config_path: str | Path | None, *, command: str) -> ContractGraph:
    project = load_project(config_path, command=command)
    if not project.entrypoints:
        raise ModuleNotFoundError(f"[{command}] 未指定蓝图entrypoints")
    build_entrypoints(project.entrypoints)
    graph = build_contract_graph(project.entrypoints)
    attach_target_context(graph, project.resolved.targets, project.resolved.project_root)
    return graph


def write_manifest(config_path: str | Path | None, out_path: Path) -> None:
    graph = load_contract_graph(config_path, command="api-gen manifest")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(graph.to_manifest(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def diff_files(before: Path, after: Path) -> dict[str, list[str]]:
    before_manifest = json.loads(before.read_text(encoding="utf-8"))
    after_manifest = json.loads(after.read_text(encoding="utf-8"))
    return diff_manifests(before_manifest, after_manifest)


def check(config_path: str | Path | None) -> None:
    resolved = resolve_config(config_path)
    graph = load_contract_graph(config_path, command="api-gen check")
    errors = capability_errors(graph, resolved.targets)
    if errors:
        raise ValueError(errors[0])


def generate(config_path: str | Path | None, target_ids: Sequence[str] = ()) -> None:
    from api_blueprint.writer import golang, kotlin, typescript
    from api_blueprint.writer.grpc.proto_writer import render_proto_files

    project = load_project(config_path, command="api-gen generate")
    if not project.entrypoints:
        raise ModuleNotFoundError("[api-gen generate] 未指定蓝图entrypoints")
    build_entrypoints(project.entrypoints)
    graph = build_contract_graph(project.entrypoints)
    attach_target_context(graph, project.resolved.targets, project.resolved.project_root)
    targets = generation_plan(project.resolved.targets, target_ids)
    errors = capability_errors(graph, targets)
    if errors:
        raise ValueError(errors[0])

    target_map = {target.id: target for target in project.resolved.targets}
    generated: set[str] = set()

    def generate_target(target: ResolvedApiTargetConfig) -> None:
        if target.id in generated:
            return

        if target.kind == "contract":
            write_contract_target(graph, target, project.resolved.project_root)
        elif target.kind == "go-server":
            output = require_out_dir(target)
            output.mkdir(parents=True, exist_ok=True)
            writer = golang.GolangWriter(
                output,
                module=target.module,
                enabled_transports=enabled_http_transports(project.resolved.targets, target.id),
                contract_graph=graph,
            )
            writer.register(*project.entrypoints)
            writer.gen()
        elif target.kind == "typescript-client":
            output = require_out_dir(target)
            output.mkdir(parents=True, exist_ok=True)
            writer = typescript.TypeScriptWriter(
                output,
                base_url=target.base_url or "",
                base_url_expr=target.base_url_expr,
                emit_http_facade=target_has_http_transport(project.resolved.targets, target.id),
                contract_graph=graph,
            )
            writer.register(*project.entrypoints)
            writer.gen()
        elif target.kind == "kotlin-client":
            output = require_out_dir(target)
            output.mkdir(parents=True, exist_ok=True)
            writer = kotlin.KotlinWriter(
                output,
                package=target.package or "",
                base_url=target.base_url or "",
                base_url_expr=target.base_url_expr,
                include=target.include,
                exclude=target.exclude,
                contract_graph=graph,
            )
            writer.register(*project.entrypoints)
            writer.gen()
        elif target.kind == "grpc-proto":
            output = require_out_dir(target)
            output.mkdir(parents=True, exist_ok=True)
            files = render_proto_files(
                graph,
                package=target.package or "",
                go_package_prefix=target.go_package_prefix or "",
            )
            for relative, text in files.items():
                file_path = output / relative
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(text, encoding="utf-8")
        elif target.kind == "wails-transport":
            if target.server is not None:
                generate_target(target_map[target.server])
            for client_id in target.clients:
                generate_target(target_map[client_id])
            generate_wails_overlay(project.entrypoints, target, target_map, graph=graph)
        elif target.kind == "http-transport":
            if target.server is not None:
                generate_target(target_map[target.server])
            for client_id in target.clients:
                generate_target(target_map[client_id])
        elif target.kind in {"python-server", "python-client", "go-client"}:
            raise ValueError(f"target[{target.id}] {target.kind} is reserved but not implemented")
        else:
            raise ValueError(f"target[{target.id}] unsupported kind: {target.kind}")

        generated.add(target.id)

    for target in targets:
        generate_target(target)


def require_target(
    targets: Sequence[ResolvedApiTargetConfig],
    target_id: str,
) -> ResolvedApiTargetConfig:
    matches = [target for target in targets if target.id == target_id]
    if len(matches) != 1:
        raise ValueError(f"target id must match exactly one target, matched {len(matches)}: {target_id}")
    return matches[0]


def selected_targets(
    targets: Sequence[ResolvedApiTargetConfig],
    target_ids: Sequence[str],
) -> tuple[ResolvedApiTargetConfig, ...]:
    if not target_ids:
        return tuple(targets)
    selected: list[ResolvedApiTargetConfig] = []
    for target_id in target_ids:
        selected.append(require_target(targets, target_id))
    return tuple(selected)


def generation_plan(
    targets: Sequence[ResolvedApiTargetConfig],
    target_ids: Sequence[str],
) -> tuple[ResolvedApiTargetConfig, ...]:
    selected = selected_targets(targets, target_ids)
    target_map = {target.id: target for target in targets}
    planned: list[ResolvedApiTargetConfig] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def target_by_id(owner: ResolvedApiTargetConfig, target_id: str) -> ResolvedApiTargetConfig:
        dependency = target_map.get(target_id)
        if dependency is None:
            raise ValueError(f"target[{owner.id}] references unknown target: {target_id}")
        return dependency

    def visit(target: ResolvedApiTargetConfig) -> None:
        if target.id in visited:
            return
        if target.id in visiting:
            raise ValueError(f"target dependency cycle detected at: {target.id}")
        visiting.add(target.id)

        if target.kind in {"http-transport", "wails-transport"}:
            if target.server is not None:
                visit(target_by_id(target, target.server))
            for client_id in target.clients:
                visit(target_by_id(target, client_id))

        visiting.remove(target.id)
        visited.add(target.id)
        planned.append(target)

    for target in selected:
        visit(target)
    return tuple(planned)


def capability_errors(
    graph: ContractGraph,
    targets: Sequence[ResolvedApiTargetConfig],
) -> list[str]:
    manifest_data = graph.to_manifest()
    routes = manifest_data["routes"]
    errors: list[str] = []
    for target in targets:
        target_capability = TARGET_CAPABILITY_REGISTRY.get(target.kind, {})
        if target_capability.get("implemented") is False:
            errors.append(f"{target.kind} is reserved but not implemented: target[{target.id}]")
            continue
        if target.kind != "kotlin-client":
            continue
        for route in routes:
            if not isinstance(route, dict):
                continue
            if not target_selects_route(target, route):
                continue
            route_id = route["id"]
            route_kind = route["kind"]
            if route_kind in {"stream", "channel"}:
                errors.append(f"kotlin-client does not support {route_kind} route: {route_id}")
                continue
            request = route.get("request") or {}
            if request.get("form_model") is not None:
                errors.append(f"kotlin-client does not support form request route: {route_id}")
            if request.get("binary_model") is not None:
                errors.append(f"kotlin-client does not support binary request route: {route_id}")
            response = route.get("response") or {}
            wrapper = response.get("wrapper")
            if wrapper not in {None, "NoneWrapper", "GeneralWrapper"}:
                errors.append(f"kotlin-client does not support custom response wrapper route: {route_id}")
    return errors


def target_selects_route(target: ResolvedApiTargetConfig, route: dict[str, object]) -> bool:
    if target.include and not any(route_matches_rule(route, rule) for rule in target.include):
        return False
    if any(route_matches_rule(route, rule) for rule in target.exclude):
        return False
    return True


def route_matches_rule(route: dict[str, object], rule: str) -> bool:
    if ":" not in rule:
        return fnmatch.fnmatchcase(str(route.get("id", "")), rule)
    key, pattern = rule.split(":", 1)
    if key == "path":
        return fnmatch.fnmatchcase(str(route.get("url", "")), pattern)
    if key == "method":
        methods = route.get("methods", [])
        return isinstance(methods, list) and any(fnmatch.fnmatchcase(str(method), pattern.upper()) for method in methods)
    if key == "group":
        return fnmatch.fnmatchcase(str(route.get("service_id", "")).rsplit(".", 1)[-1], pattern)
    if key == "name":
        return fnmatch.fnmatchcase(str(route.get("operation", "")), pattern)
    if key == "kind":
        return fnmatch.fnmatchcase(str(route.get("kind", "")), pattern)
    return False


def write_contract_target(graph: ContractGraph, target: ResolvedApiTargetConfig, project_root: Path) -> None:
    out_dir = target.out_dir or project_root
    out_dir.mkdir(parents=True, exist_ok=True)
    formats = target.formats or ("json",)
    manifest_data = graph.to_manifest()
    if "json" in formats:
        (out_dir / "api-blueprint.contract.json").write_text(
            json.dumps(manifest_data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if "markdown" in formats:
        (out_dir / "api-blueprint.contract.md").write_text(render_contract_markdown(manifest_data), encoding="utf-8")


def render_contract_markdown(manifest_data: dict[str, object]) -> str:
    lines = ["# api-blueprint Contract", ""]
    for route in manifest_data.get("routes", []):
        if not isinstance(route, dict):
            continue
        lines.append(f"- `{route.get('id')}` `{route.get('kind')}` `{route.get('url')}`")
    lines.append("")
    return "\n".join(lines)


def attach_target_context(
    graph: ContractGraph,
    targets: Sequence[ResolvedApiTargetConfig],
    project_root: Path,
) -> None:
    graph.targets = [target_manifest(target, project_root) for target in targets]
    graph.capabilities = {name: dict(capability) for name, capability in TARGET_CAPABILITY_REGISTRY.items()}


def target_manifest(target: ResolvedApiTargetConfig, project_root: Path) -> dict[str, object]:
    manifest: dict[str, object] = {
        "id": target.id,
        "kind": target.kind,
    }
    if target.out_dir is not None:
        manifest["out_dir"] = _portable_path(target.out_dir, project_root)
    if target.module is not None:
        manifest["module"] = target.module
    if target.base_url is not None:
        manifest["base_url"] = target.base_url
    if target.base_url_expr is not None:
        manifest["base_url_expr"] = target.base_url_expr
    if target.package is not None:
        manifest["package"] = target.package
    if target.formats:
        manifest["formats"] = list(target.formats)
    if target.version is not None:
        manifest["version"] = target.version
    if target.kind == "wails-transport":
        manifest["frontend_mode"] = target.frontend_mode
    if target.overlay_name is not None:
        manifest["overlay_name"] = target.overlay_name
    if target.server is not None:
        manifest["server"] = target.server
    if target.clients:
        manifest["clients"] = list(target.clients)
    if target.go_package_prefix is not None:
        manifest["go_package_prefix"] = target.go_package_prefix
    if target.include:
        manifest["include"] = list(target.include)
    if target.exclude:
        manifest["exclude"] = list(target.exclude)
    return manifest


def _portable_path(path: Path, project_root: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = project_root.resolve()
    try:
        relative = resolved_path.relative_to(resolved_root)
    except ValueError:
        return resolved_path.as_posix()
    return "." if relative == Path(".") else relative.as_posix()


def require_out_dir(target: ResolvedApiTargetConfig) -> Path:
    if target.out_dir is None:
        raise ValueError(f"target[{target.id}] requires out_dir")
    return target.out_dir


def enabled_http_transports(targets: Sequence[ResolvedApiTargetConfig], server_id: str) -> tuple[str, ...]:
    return ("http",) if any(
        target.kind == "http-transport" and target.server == server_id for target in targets
    ) else ()


def target_has_http_transport(targets: Sequence[ResolvedApiTargetConfig], client_id: str) -> bool:
    return any(
        target.kind == "http-transport" and client_id in target.clients for target in targets
    )


def generate_wails_overlay(
    entrypoints: list[Blueprint],
    target: ResolvedApiTargetConfig,
    target_map: dict[str, ResolvedApiTargetConfig],
    *,
    graph: ContractGraph,
) -> None:
    from api_blueprint.writer import wails

    if target.server is None:
        raise ValueError(f"target[{target.id}] wails-transport requires server")
    if not target.clients:
        raise ValueError(f"target[{target.id}] wails-transport requires at least one client")
    server = target_map[target.server]
    client = target_map[target.clients[0]]
    if server.out_dir is None:
        raise ValueError(f"target[{target.id}] server target[{server.id}] requires out_dir")
    if client.out_dir is None:
        raise ValueError(f"target[{target.id}] client target[{client.id}] requires out_dir")
    wails_config = ResolvedWailsConfig(
        targets=(
            ResolvedWailsTargetConfig(
                id=target.id,
                version=target.version or "v3",
                overlay_name=target.overlay_name or f"wails{target.version or 'v3'}",
                frontend_mode=target.frontend_mode,
                include=target.include,
                exclude=target.exclude,
            ),
        )
    )
    writer = wails.WailsWriter(wails_config, contract_graph=graph)
    writer.gen(
        entrypoints,
        golang_config=ResolvedTargetConfig(output=server.out_dir, module=server.module),
        typescript_config=ResolvedTargetConfig(
            output=client.out_dir,
            base_url=client.base_url,
            base_url_expr=client.base_url_expr,
        ),
        target_patterns=(target.id,),
    )
