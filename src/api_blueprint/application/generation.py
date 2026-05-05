from __future__ import annotations

from pathlib import Path
from typing import Sequence

from api_blueprint.application.docs import run_docs_server
from api_blueprint.application.project import build_entrypoints, load_project
from api_blueprint.config import (
    ResolvedConfig,
    ResolvedGrpcConfig,
    ResolvedGrpcJobConfig,
    ResolvedGrpcTargetConfig,
    ResolvedKotlinConfig,
    ResolvedTargetConfig,
    ResolvedWailsConfig,
    ResolvedWailsTargetConfig,
    resolve_config,
)
from api_blueprint.writer.grpc.models import GrpcGenerationJob
from api_blueprint.writer.wails.models import WailsGenerationTarget


def _require_golang_config(resolved: ResolvedConfig) -> ResolvedTargetConfig:
    if resolved.raw.golang is None or resolved.golang is None:
        raise ValueError("[gen_golang] 配置中未找到golang段落")
    return resolved.golang


def _require_typescript_config(resolved: ResolvedConfig) -> ResolvedTargetConfig:
    if resolved.raw.typescript is None or resolved.typescript is None:
        raise ValueError("[gen_typescript] 配置中未找到typescript段落")
    return resolved.typescript


def _require_kotlin_config(resolved: ResolvedConfig) -> ResolvedKotlinConfig:
    if resolved.raw.kotlin is None or resolved.kotlin is None:
        raise ValueError("[gen_kotlin] 配置中未找到kotlin段落")
    return resolved.kotlin


def _require_grpc_config(resolved: ResolvedConfig) -> ResolvedGrpcConfig:
    if resolved.raw.grpc is None or resolved.grpc is None:
        raise ValueError("[gen_grpc] 配置中未找到grpc段落")
    return resolved.grpc


def _require_wails_config(resolved: ResolvedConfig) -> ResolvedWailsConfig:
    if resolved.wails is None or not resolved.wails.targets:
        raise ValueError("[gen_wails] 配置中未找到 kind='wails' 的 [[transport.targets]]")
    return resolved.wails


def _golang_enabled_transports(resolved: ResolvedConfig) -> tuple[str, ...]:
    targets = resolved.transport.targets
    if not targets:
        return ("http",)
    return ("http",) if any(target.kind == "http" for target in targets) else ()


def _emit_http_transport(resolved: ResolvedConfig) -> bool:
    targets = resolved.transport.targets
    return not targets or any(target.kind == "http" for target in targets)


def generate_golang(config_path: str | Path | None = "./api-blueprint.toml", *, doc: bool = False) -> None:
    from api_blueprint.writer import golang

    resolved = resolve_config(config_path)
    golang_config = _require_golang_config(resolved)
    output = golang_config.output
    if output is None:
        raise FileNotFoundError("[gen_golang] --output 输出路径[None]不存在")
    if not output.exists():
        raise FileNotFoundError(f"[gen_golang] --output 输出路径[{output}]不存在")

    project = load_project(resolved.path, command="gen_golang")
    if not project.entrypoints:
        raise ModuleNotFoundError("[gen_golang] 未指定蓝图entrypoints")
    build_entrypoints(project.entrypoints)
    writer = golang.GolangWriter(
        output,
        module=golang_config.module,
        enabled_transports=_golang_enabled_transports(resolved),
    )
    writer.register(*project.entrypoints)
    writer.gen()

    if doc:
        run_docs_server(project.config, project.entrypoints)


def generate_typescript(config_path: str | Path | None = "./api-blueprint.toml", *, doc: bool = False) -> None:
    from api_blueprint.writer import typescript

    resolved = resolve_config(config_path)
    typescript_config = _require_typescript_config(resolved)
    output = typescript_config.output
    if output is None:
        raise FileNotFoundError("[gen_typescript] --output 输出路径[None]不存在")
    if not output.exists():
        raise FileNotFoundError(f"[gen_typescript] --output 输出路径[{output}]不存在")

    project = load_project(resolved.path, command="gen_typescript")
    if not project.entrypoints:
        raise ModuleNotFoundError("[gen_typescript] 未指定蓝图entrypoints")
    build_entrypoints(project.entrypoints)
    base_url = typescript_config.base_url or typescript_config.upstream or ""
    writer = typescript.TypeScriptWriter(
        output,
        base_url=base_url,
        base_url_expr=typescript_config.base_url_expr,
        emit_http_facade=_emit_http_transport(resolved),
    )
    writer.register(*project.entrypoints)
    writer.gen()

    if doc:
        run_docs_server(project.config, project.entrypoints)


def generate_kotlin(config_path: str | Path | None = "./api-blueprint.toml", *, doc: bool = False) -> None:
    from api_blueprint.writer import kotlin

    resolved = resolve_config(config_path)
    kotlin_config = _require_kotlin_config(resolved)
    output = kotlin_config.output
    if output is None:
        raise FileNotFoundError("[gen_kotlin] --output 输出路径[None]不存在")
    if not output.exists():
        raise FileNotFoundError(f"[gen_kotlin] --output 输出路径[{output}]不存在")

    project = load_project(resolved.path, command="gen_kotlin")
    if not project.entrypoints:
        raise ModuleNotFoundError("[gen_kotlin] 未指定蓝图entrypoints")
    build_entrypoints(project.entrypoints)
    base_url = kotlin_config.base_url or kotlin_config.upstream or ""
    writer = kotlin.KotlinWriter(
        output,
        package=kotlin_config.package,
        base_url=base_url,
        base_url_expr=kotlin_config.base_url_expr,
        include=kotlin_config.include,
        exclude=kotlin_config.exclude,
        allow_empty=kotlin_config.allow_empty,
    )
    writer.register(*project.entrypoints)
    writer.gen()

    if doc:
        run_docs_server(project.config, project.entrypoints)


def list_grpc_jobs(
    config_path: str | Path | None = "./api-blueprint.toml",
    *,
    job_filters: Sequence[str] = (),
) -> tuple[ResolvedGrpcJobConfig, ...]:
    from api_blueprint.writer import grpc

    resolved = resolve_config(config_path)
    grpc_config = _require_grpc_config(resolved)
    writer = grpc.GrpcWriter(grpc_config)
    return writer.list_jobs(job_filters)


def list_grpc_targets(
    config_path: str | Path | None = "./api-blueprint.toml",
    *,
    target_filters: Sequence[str] = (),
) -> tuple[ResolvedGrpcTargetConfig, ...]:
    from api_blueprint.writer import grpc

    resolved = resolve_config(config_path)
    grpc_config = _require_grpc_config(resolved)
    writer = grpc.GrpcWriter(grpc_config)
    return writer.list_targets(target_filters)


def explain_grpc_target(
    config_path: str | Path | None = "./api-blueprint.toml",
    *,
    target_id: str,
) -> GrpcGenerationJob:
    from api_blueprint.writer import grpc

    resolved = resolve_config(config_path)
    grpc_config = _require_grpc_config(resolved)
    writer = grpc.GrpcWriter(grpc_config)
    return writer.explain_target(target_id)


def generate_grpc(
    config_path: str | Path | None = "./api-blueprint.toml",
    *,
    target_filters: Sequence[str] = (),
    job_filters: Sequence[str] = (),
) -> None:
    from api_blueprint.writer import grpc

    resolved = resolve_config(config_path)
    grpc_config = _require_grpc_config(resolved)
    writer = grpc.GrpcWriter(grpc_config)
    writer.gen(target_patterns=target_filters, job_patterns=job_filters)


def list_wails_targets(
    config_path: str | Path | None = "./api-blueprint.toml",
    *,
    target_filters: Sequence[str] = (),
) -> tuple[ResolvedWailsTargetConfig, ...]:
    from api_blueprint.writer import wails

    resolved = resolve_config(config_path)
    wails_config = _require_wails_config(resolved)
    writer = wails.WailsWriter(wails_config)
    return writer.list_targets(target_filters)


def explain_wails_target(
    config_path: str | Path | None = "./api-blueprint.toml",
    *,
    target_id: str,
) -> WailsGenerationTarget:
    from api_blueprint.writer import wails

    resolved = resolve_config(config_path)
    wails_config = _require_wails_config(resolved)
    golang_config = _require_golang_config(resolved)
    typescript_config = _require_typescript_config(resolved)
    writer = wails.WailsWriter(wails_config)
    return writer.explain_target(target_id, golang_config=golang_config, typescript_config=typescript_config)


def generate_wails(
    config_path: str | Path | None = "./api-blueprint.toml",
    *,
    target_filters: Sequence[str] = (),
) -> tuple[WailsGenerationTarget, ...]:
    from api_blueprint.writer import golang, typescript, wails

    resolved = resolve_config(config_path)
    wails_config = _require_wails_config(resolved)
    golang_config = _require_golang_config(resolved)
    typescript_config = _require_typescript_config(resolved)
    golang_output = golang_config.output
    typescript_output = typescript_config.output
    if golang_output is None:
        raise FileNotFoundError("[gen_wails] 共享 Go 契约层要求 [golang].codegen_output 不能为 None")
    if not golang_output.exists():
        raise FileNotFoundError(f"[gen_wails] 共享 Go 契约层输出路径[{golang_output}]不存在")
    if typescript_output is None:
        raise FileNotFoundError("[gen_wails] 共享 TypeScript 契约层要求 [typescript].codegen_output 不能为 None")
    if not typescript_output.exists():
        raise FileNotFoundError(f"[gen_wails] 共享 TypeScript 契约层输出路径[{typescript_output}]不存在")

    project = load_project(resolved.path, command="gen_wails")
    if not project.entrypoints:
        raise ModuleNotFoundError("[gen_wails] 未指定蓝图entrypoints")
    build_entrypoints(project.entrypoints)

    go_writer = golang.GolangWriter(
        golang_output,
        module=golang_config.module,
        enabled_transports=_golang_enabled_transports(resolved),
    )
    go_writer.register(*project.entrypoints)
    go_writer.gen()

    base_url = typescript_config.base_url or typescript_config.upstream or ""
    ts_writer = typescript.TypeScriptWriter(
        typescript_output,
        base_url=base_url,
        base_url_expr=typescript_config.base_url_expr,
        emit_http_facade=_emit_http_transport(resolved),
    )
    ts_writer.register(*project.entrypoints)
    ts_writer.gen()

    writer = wails.WailsWriter(wails_config)
    return writer.gen(
        project.entrypoints,
        golang_config=golang_config,
        typescript_config=typescript_config,
        target_patterns=target_filters,
    )
