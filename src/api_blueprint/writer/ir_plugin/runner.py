from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, cast

from api_blueprint.config import ResolvedApiTargetConfig
from api_blueprint.contract import ContractGraph
from api_blueprint.writer.core.planning import target_selects_route
from api_blueprint.writer.ir_plugin.context import IrPluginContext


IrPluginGenerate = Callable[[IrPluginContext], None]


def validate_ir_plugin_target(target: ResolvedApiTargetConfig, project_root: Path) -> None:
    _load_generate(target, project_root)


def run_ir_plugin(graph: ContractGraph, target: ResolvedApiTargetConfig, project_root: Path) -> None:
    generate = _load_generate(target, project_root)
    out_dir = _require_out_dir(target)
    out_dir.mkdir(parents=True, exist_ok=True)
    routes = [route for route in graph.to_manifest()["routes"] if target_selects_route(target, route)]
    context = IrPluginContext(
        contract_graph=graph,
        target=target,
        project_root=project_root,
        out_dir=out_dir,
        selected_routes=tuple(routes),
        options=dict(target.options),
    )
    generate(context)


def _load_generate(target: ResolvedApiTargetConfig, project_root: Path) -> IrPluginGenerate:
    if not target.plugin:
        raise ValueError(f"target[{target.id}] ir-plugin requires plugin")
    with import_path_scope(project_root):
        module = importlib.import_module(target.plugin)
    generate = getattr(module, "generate", None)
    if not callable(generate):
        raise TypeError(f"target[{target.id}] ir-plugin module {target.plugin!r} must expose generate(context)")
    return cast(IrPluginGenerate, generate)


def _require_out_dir(target: ResolvedApiTargetConfig) -> Path:
    if target.out_dir is None:
        raise ValueError(f"target[{target.id}] ir-plugin requires out_dir")
    return target.out_dir


@contextmanager
def import_path_scope(*paths: Path) -> Generator[None, None, None]:
    added: list[str] = []
    try:
        for path in paths:
            value = str(path.resolve())
            if value not in sys.path:
                sys.path.insert(0, value)
                added.append(value)
        yield
    finally:
        for value in reversed(added):
            if value in sys.path:
                sys.path.remove(value)
