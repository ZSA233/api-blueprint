from __future__ import annotations

from pathlib import Path
from typing import Sequence

from api_blueprint.application.docs import run_docs_server
from api_blueprint.application.project import build_entrypoints, load_project
from api_blueprint.config import ResolvedConfig, ResolvedGrpcConfig, ResolvedGrpcJobConfig, ResolvedTargetConfig, resolve_config


def _require_golang_config(resolved: ResolvedConfig) -> ResolvedTargetConfig:
    if resolved.raw.golang is None or resolved.golang is None:
        raise ValueError("[gen_golang] 配置中未找到golang段落")
    return resolved.golang


def _require_typescript_config(resolved: ResolvedConfig) -> ResolvedTargetConfig:
    if resolved.raw.typescript is None or resolved.typescript is None:
        raise ValueError("[gen_typescript] 配置中未找到typescript段落")
    return resolved.typescript


def _require_grpc_config(resolved: ResolvedConfig) -> ResolvedGrpcConfig:
    if resolved.raw.grpc is None or resolved.grpc is None:
        raise ValueError("[gen_grpc] 配置中未找到grpc段落")
    return resolved.grpc


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
    writer = golang.GolangWriter(output, module=golang_config.module)
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


def generate_grpc(
    config_path: str | Path | None = "./api-blueprint.toml",
    *,
    job_filters: Sequence[str] = (),
) -> None:
    from api_blueprint.writer import grpc

    resolved = resolve_config(config_path)
    grpc_config = _require_grpc_config(resolved)
    writer = grpc.GrpcWriter(grpc_config)
    writer.gen(job_filters)
