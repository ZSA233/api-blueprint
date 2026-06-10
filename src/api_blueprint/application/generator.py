from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Sequence

from api_blueprint.application.entrypoints import load_entrypoints
from api_blueprint.application.project import LoadedProject, build_entrypoints, load_project
from api_blueprint.config import ResolvedApiTargetConfig, ResolvedTargetConfig, resolve_config
from api_blueprint.config.resolved import ResolvedWailsConfig, ResolvedWailsTargetConfig
from api_blueprint.contract import (
    ContractGraph,
    build_agent_manifest,
    build_contract_graph,
    build_contract_shards,
    build_index_manifest,
    diff_manifests,
    render_agent_markdown,
)
from api_blueprint.engine import Blueprint
from api_blueprint.writer.core.planning import (
    capability_errors,
    target_capability_manifest,
    target_selects_route,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("ApplicationGenerator")
logger.setLevel(logging.INFO)


TARGET_CAPABILITY_REGISTRY: dict[str, dict[str, object]] = target_capability_manifest()

EXPLAIN_TARGET_KIND_FIELDS: dict[str, tuple[str, ...]] = {
    "contract": ("formats",),
    "go-server": ("module",),
    "go-client": ("module", "base_url", "base_url_expr", "include", "exclude"),
    "typescript-client": ("base_url", "base_url_expr", "include", "exclude"),
    "kotlin-client": ("package", "base_url", "base_url_expr", "include", "exclude"),
    "java-server": (
        "package",
        "spring_contract_mode",
        "spring_policy_mappings",
        "spring_public_paths",
        "spring_exclude_server_paths",
        "include",
        "exclude",
    ),
    "java-client": ("package", "base_url", "base_url_expr", "include", "exclude"),
    "flutter-client": ("package", "base_url", "base_url_expr", "include", "exclude"),
    "swift-client": ("package", "module", "base_url", "base_url_expr", "runtime_profile", "include", "exclude"),
    "python-server": ("python_package_root", "include", "exclude"),
    "python-client": ("python_package_root", "base_url", "base_url_expr", "include", "exclude"),
    "http-transport": ("server", "clients"),
    "wails-transport": ("version", "overlay_name", "frontend_mode", "server", "clients", "include", "exclude"),
    "grpc-proto": ("package", "go_package_prefix", "proto_files"),
    "grpc-go": ("proto", "source_root", "files", "import_roots", "module"),
    "grpc-python": ("proto", "source_root", "files", "import_roots", "python_package_root"),
}

EXPLAIN_TARGET_LIST_FIELDS = {
    "formats",
    "clients",
    "files",
    "import_roots",
    "include",
    "exclude",
    "proto_files",
    "spring_policy_mappings",
    "spring_public_paths",
    "spring_exclude_server_paths",
}


def list_targets(config_path: str | Path | None) -> tuple[ResolvedApiTargetConfig, ...]:
    return resolve_config(config_path).targets


def explain_target(config_path: str | Path | None, target_id: str) -> ResolvedApiTargetConfig:
    return require_target(resolve_config(config_path).targets, target_id)


def explain_target_summary(config_path: str | Path | None, target_id: str) -> dict[str, Any]:
    resolved = resolve_config(config_path)
    target = require_target(resolved.targets, target_id)
    manifest = target_manifest(target, resolved.project_root)
    fields = ("id", "kind", "out_dir", *EXPLAIN_TARGET_KIND_FIELDS.get(target.kind, ()))
    summary: dict[str, Any] = {}
    for field in fields:
        value = _effective_target_summary_value(field, target, manifest)
        if value is None:
            continue
        summary[field] = value
    return summary


def load_contract_graph(config_path: str | Path | None, *, command: str) -> ContractGraph:
    project = load_project(config_path, command=command)
    if not project.entrypoints:
        raise ModuleNotFoundError(f"[{command}] 未指定蓝图entrypoints")
    build_entrypoints(project.entrypoints)
    graph = build_contract_graph(project.entrypoints)
    attach_target_context(graph, project.resolved.targets, project.resolved.project_root)
    return graph


def write_manifest(
    config_path: str | Path | None,
    out_path: Path | None,
    *,
    profile: str = "full",
    shards_dir: Path | None = None,
) -> None:
    graph = load_contract_graph(config_path, command="api-gen manifest")
    manifest_data = graph.to_manifest()
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if profile == "agent":
            payload = build_agent_manifest(manifest_data)
        elif profile == "index":
            payload = build_index_manifest(manifest_data)
        else:
            payload = manifest_data
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if shards_dir is not None:
        write_contract_shards(manifest_data, shards_dir)


def diff_files(before: Path, after: Path) -> dict[str, list[str]]:
    before_manifest = json.loads(before.read_text(encoding="utf-8"))
    after_manifest = json.loads(after.read_text(encoding="utf-8"))
    return diff_manifests(before_manifest, after_manifest)


def check(config_path: str | Path | None) -> None:
    resolved = resolve_config(config_path)
    if not _target_plan_requires_blueprint(resolved.targets):
        return
    graph = load_contract_graph(config_path, command="api-gen check")
    errors = capability_errors(graph, resolved.targets)
    if errors:
        raise ValueError(errors[0])


def generate(config_path: str | Path | None, target_ids: Sequence[str] = ()) -> None:
    from api_blueprint.writer import flutter, golang, java, kotlin, python as python_writer, swift, typescript
    from api_blueprint.writer.grpc.proto_writer import render_proto_files, write_proto_files
    from api_blueprint.writer.grpc import toolchain as grpc_toolchain

    resolved = resolve_config(config_path)
    targets = generation_plan(resolved.targets, target_ids)
    project, graph = _load_project_for_generation(config_path, targets)
    if graph is not None:
        attach_target_context(graph, project.resolved.targets, project.resolved.project_root)
        errors = capability_errors(graph, targets)
        if errors:
            raise ValueError(errors[0])

    target_map = {target.id: target for target in project.resolved.targets}
    generated: set[str] = set()

    def generate_target(target: ResolvedApiTargetConfig) -> None:
        if target.id in generated:
            logger.info("[.] Skipped target: %s (already generated)", target.id)
            return
        logger.info("[*] Generating target: %s (%s)", target.id, target.kind)

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
        elif target.kind == "go-client":
            output = require_out_dir(target)
            output.mkdir(parents=True, exist_ok=True)
            writer = golang.GolangClientWriter(
                output,
                module=target.module,
                base_url=target.base_url or "",
                base_url_expr=target.base_url_expr,
                include=target.include,
                exclude=target.exclude,
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
                include=target.include,
                exclude=target.exclude,
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
        elif target.kind == "kotlin-server":
            output = require_out_dir(target)
            output.mkdir(parents=True, exist_ok=True)
            writer = kotlin.KotlinServerWriter(
                output,
                package=target.package or "",
                include=target.include,
                exclude=target.exclude,
                contract_graph=graph,
            )
            writer.register(*project.entrypoints)
            writer.gen()
        elif target.kind == "java-client":
            output = require_out_dir(target)
            output.mkdir(parents=True, exist_ok=True)
            writer = java.JavaClientWriter(
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
        elif target.kind == "java-server":
            output = require_out_dir(target)
            output.mkdir(parents=True, exist_ok=True)
            writer = java.JavaServerWriter(
                output,
                package=target.package or "",
                include=target.include,
                exclude=target.exclude,
                contract_graph=graph,
                spring_contract_mode=target.spring_contract_mode,
                spring_policy_mappings=target.spring_policy_mappings,
                spring_public_paths=target.spring_public_paths,
                spring_exclude_server_paths=target.spring_exclude_server_paths,
            )
            writer.register(*project.entrypoints)
            writer.gen()
        elif target.kind == "flutter-client":
            output = require_out_dir(target)
            output.mkdir(parents=True, exist_ok=True)
            writer = flutter.FlutterWriter(
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
        elif target.kind == "swift-client":
            output = require_out_dir(target)
            output.mkdir(parents=True, exist_ok=True)
            writer = swift.SwiftWriter(
                output,
                package=target.package or "",
                module=target.module,
                base_url=target.base_url or "",
                base_url_expr=target.base_url_expr,
                runtime_profile=target.runtime_profile,
                include=target.include,
                exclude=target.exclude,
                contract_graph=graph,
            )
            writer.register(*project.entrypoints)
            writer.gen()
        elif target.kind == "python-client":
            output = require_out_dir(target)
            output.mkdir(parents=True, exist_ok=True)
            writer = python_writer.PythonClientWriter(
                output,
                python_package_root=target.python_package_root,
                base_url=target.base_url or "",
                base_url_expr=target.base_url_expr,
                include=target.include,
                exclude=target.exclude,
                contract_graph=graph,
            )
            writer.register(*project.entrypoints)
            writer.gen()
        elif target.kind == "python-server":
            output = require_out_dir(target)
            output.mkdir(parents=True, exist_ok=True)
            writer = python_writer.PythonServerWriter(
                output,
                python_package_root=target.python_package_root,
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
                proto_files=target.proto_files,
                include=target.include,
                exclude=target.exclude,
            )
            write_proto_files(output, files)
        elif target.kind in {"grpc-go", "grpc-python"}:
            if target.proto is not None:
                proto_target = target_map[target.proto]
                generate_target(proto_target)
                proto_root = require_out_dir(proto_target)
            else:
                proto_root = require_source_root(target)
            if target.kind == "grpc-go":
                grpc_toolchain.generate_go_stubs(proto_root, target)
            else:
                grpc_toolchain.generate_python_stubs(proto_root, target)
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
        else:
            raise ValueError(f"target[{target.id}] unsupported kind: {target.kind}")

        generated.add(target.id)

    for target in targets:
        generate_target(target)


def _load_project_for_generation(
    config_path: str | Path | None,
    targets: Sequence[ResolvedApiTargetConfig],
) -> tuple[LoadedProject, ContractGraph | None]:
    resolved = resolve_config(config_path)
    if not _target_plan_requires_blueprint(targets):
        return LoadedProject(config=resolved.raw, resolved=resolved, entrypoints=[]), None

    if resolved.raw.blueprint is None:
        raise ValueError("[api-gen generate] 配置中未找到blueprint段落")
    entrypoints = load_entrypoints(resolved.raw.blueprint.entrypoints, resolved.entrypoint_root)
    if not entrypoints:
        raise ModuleNotFoundError("[api-gen generate] 未指定蓝图entrypoints")
    build_entrypoints(entrypoints)
    graph = build_contract_graph(entrypoints)
    return LoadedProject(config=resolved.raw, resolved=resolved, entrypoints=entrypoints), graph


def _target_plan_requires_blueprint(targets: Sequence[ResolvedApiTargetConfig]) -> bool:
    for target in targets:
        if target.kind in {"grpc-go", "grpc-python"} and target.proto is None:
            continue
        return True
    return False


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
        if target.kind in {"grpc-go", "grpc-python"} and target.proto is not None:
            visit(target_by_id(target, target.proto))

        visiting.remove(target.id)
        visited.add(target.id)
        planned.append(target)

    for target in selected:
        visit(target)
    return tuple(planned)


def write_contract_target(graph: ContractGraph, target: ResolvedApiTargetConfig, project_root: Path) -> None:
    out_dir = target.out_dir or project_root
    out_dir.mkdir(parents=True, exist_ok=True)
    formats = target.formats or ("index",)
    manifest_data = graph.to_manifest()
    if "index" in formats:
        (out_dir / "api-blueprint.index.json").write_text(
            json.dumps(build_index_manifest(manifest_data), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if "json" in formats:
        (out_dir / "api-blueprint.contract.json").write_text(
            json.dumps(manifest_data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if "markdown" in formats:
        (out_dir / "api-blueprint.contract.md").write_text(render_contract_markdown(manifest_data), encoding="utf-8")
    if "agent-json" in formats:
        (out_dir / "api-blueprint.agent.json").write_text(
            json.dumps(build_agent_manifest(manifest_data), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if "agent-markdown" in formats:
        (out_dir / "api-blueprint.agent.md").write_text(render_agent_markdown(manifest_data), encoding="utf-8")
    if "shards" in formats:
        write_contract_shards(manifest_data, out_dir / "api-blueprint.contract.d")


def render_contract_markdown(manifest_data: dict[str, object]) -> str:
    lines = ["# api-blueprint Contract", ""]
    for route in manifest_data.get("routes", []):
        if not isinstance(route, dict):
            continue
        lines.append(f"- `{route.get('id')}` `{route.get('kind')}` `{route.get('url')}`")
    lines.append("")
    return "\n".join(lines)


def write_contract_shards(manifest_data: dict[str, object], shards_dir: Path) -> None:
    shutil.rmtree(shards_dir, ignore_errors=True)
    shards = build_contract_shards(manifest_data)
    for relative, payload in shards.items():
        path = shards_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
        if target.kind in {"go-server", "go-client"} and target.out_dir is not None:
            manifest["go_import_root"] = _derive_go_import_root(
                target.module,
                _portable_path(target.out_dir, project_root),
                target.out_dir,
            )
    if target.base_url is not None:
        manifest["base_url"] = target.base_url
    if target.base_url_expr is not None:
        manifest["base_url_expr"] = target.base_url_expr
    if target.package is not None:
        manifest["package"] = target.package
    if target.kind == "swift-client":
        manifest["runtime_profile"] = target.runtime_profile
    if target.kind == "java-server":
        manifest["spring_contract_mode"] = target.spring_contract_mode
        if target.spring_policy_mappings:
            manifest["spring_policy_mappings"] = [
                {
                    key: value
                    for key, value in {
                        "provider": mapping.provider,
                        "annotation": mapping.annotation,
                        "args": mapping.args,
                        "imports": list(mapping.imports),
                    }.items()
                    if value is not None and value != []
                }
                for mapping in target.spring_policy_mappings
            ]
        if target.spring_public_paths:
            manifest["spring_public_paths"] = list(target.spring_public_paths)
        if target.spring_exclude_server_paths:
            manifest["spring_exclude_server_paths"] = list(target.spring_exclude_server_paths)
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
    if target.proto is not None:
        manifest["proto"] = target.proto
    if target.source_root is not None and target.kind in {"grpc-go", "grpc-python"}:
        manifest["source_root"] = _portable_path(target.source_root, project_root)
    if target.files:
        manifest["files"] = list(target.files)
    if target.import_roots:
        manifest["import_roots"] = [_portable_path(path, project_root) for path in target.import_roots]
    if target.go_package_prefix is not None:
        manifest["go_package_prefix"] = target.go_package_prefix
    if target.proto_files:
        manifest["proto_files"] = [
            {
                key: value
                for key, value in {
                    "file": proto_file.file,
                    "package": proto_file.package,
                    "go_package": proto_file.go_package,
                    "schema_modules": list(proto_file.schema_modules),
                    "schema_names": list(proto_file.schema_names),
                    "route_paths": list(proto_file.route_paths),
                    "route_ids": list(proto_file.route_ids),
                    "service_ids": list(proto_file.service_ids),
                    "service": proto_file.service,
                }.items()
                if value is not None and value != []
            }
            for proto_file in target.proto_files
        ]
    if target.python_package_root is not None:
        manifest["python_package_root"] = target.python_package_root
    if target.include:
        manifest["include"] = list(target.include)
    if target.exclude:
        manifest["exclude"] = list(target.exclude)
    return manifest


def _effective_target_summary_value(
    field: str,
    target: ResolvedApiTargetConfig,
    manifest: dict[str, object],
) -> Any:
    if field in manifest:
        return manifest[field]
    if field == "formats" and target.kind == "contract":
        return ["index"]
    if field in EXPLAIN_TARGET_LIST_FIELDS:
        return []
    if field == "frontend_mode" and target.kind == "wails-transport":
        return target.frontend_mode
    return None


def _portable_path(path: Path, project_root: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = project_root.resolve()
    try:
        relative_path = os.path.relpath(resolved_path, resolved_root)
    except ValueError:
        return resolved_path.as_posix()
    if relative_path == ".":
        return "."
    return Path(relative_path).as_posix()


def _derive_go_import_root(module: str, out_dir: str, out_path: Path | None = None) -> str:
    if out_path is not None:
        module_root = _find_nearest_go_module_root(out_path)
        if module_root is not None:
            try:
                relative = out_path.resolve().relative_to(module_root)
            except ValueError:
                relative = Path(".")
            relative_parts = [part for part in relative.as_posix().split("/") if part and part != "."]
            return "/".join([module, *relative_parts]) if relative_parts else module

    out_parts = [
        part
        for part in Path(out_dir).as_posix().split("/")
        if part and part not in {".", ".."}
    ]
    if not out_parts:
        return module

    module_parts = [part for part in module.split("/") if part]
    matched = 0
    max_match = min(len(module_parts), len(out_parts))
    for size in range(1, max_match + 1):
        if module_parts[-size:] == out_parts[:size]:
            matched = size
    extra_parts = out_parts[matched:]
    return "/".join([module, *extra_parts]) if extra_parts else module


def _find_nearest_go_module_root(path: Path) -> Path | None:
    resolved = path.resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / "go.mod").is_file():
            return candidate
    return None


def require_out_dir(target: ResolvedApiTargetConfig) -> Path:
    if target.out_dir is None:
        raise ValueError(f"target[{target.id}] requires out_dir")
    return target.out_dir


def require_source_root(target: ResolvedApiTargetConfig) -> Path:
    if target.source_root is None:
        raise ValueError(f"target[{target.id}] {target.kind} requires source_root when proto is omitted")
    return target.source_root


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
