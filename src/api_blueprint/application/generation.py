from __future__ import annotations

from pathlib import Path

from api_blueprint.application.docs import run_docs_server
from api_blueprint.application.project import build_entrypoints, load_project
from api_blueprint.config import resolve_config


def generate_golang(config_path: str | Path | None = "./api-blueprint.toml", *, doc: bool = False) -> None:
    from api_blueprint.writer import golang

    resolved = resolve_config(config_path)
    output = resolved.golang.output
    if output is None:
        raise FileNotFoundError("[gen_golang] --output 输出路径[None]不存在")
    if not output.exists():
        raise FileNotFoundError(f"[gen_golang] --output 输出路径[{output}]不存在")

    project = load_project(resolved.path)
    if not project.entrypoints:
        raise ModuleNotFoundError("[gen_golang] 未指定蓝图entrypoints")
    build_entrypoints(project.entrypoints)
    writer = golang.GolangWriter(output, module=resolved.golang.module)
    writer.register(*project.entrypoints)
    writer.gen()

    if doc:
        run_docs_server(project.config, project.entrypoints)


def generate_typescript(config_path: str | Path | None = "./api-blueprint.toml", *, doc: bool = False) -> None:
    from api_blueprint.writer import typescript

    resolved = resolve_config(config_path)
    if resolved.raw.typescript is None or resolved.typescript is None:
        raise ValueError("[gen_typescript] 配置中未找到typescript段落")

    output = resolved.typescript.output
    if output is None:
        raise FileNotFoundError("[gen_typescript] --output 输出路径[None]不存在")
    if not output.exists():
        raise FileNotFoundError(f"[gen_typescript] --output 输出路径[{output}]不存在")

    project = load_project(resolved.path)
    if not project.entrypoints:
        raise ModuleNotFoundError("[gen_typescript] 未指定蓝图entrypoints")
    build_entrypoints(project.entrypoints)
    base_url = resolved.typescript.base_url or resolved.typescript.upstream or ""
    writer = typescript.TypeScriptWriter(output, base_url=base_url)
    writer.register(*project.entrypoints)
    writer.gen()

    if doc:
        run_docs_server(project.config, project.entrypoints)
