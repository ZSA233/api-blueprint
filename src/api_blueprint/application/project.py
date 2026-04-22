from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from api_blueprint.config import BlueprintConfig, Config, ResolvedConfig, resolve_config
from api_blueprint.engine import Blueprint

from .entrypoints import load_entrypoints


@dataclass(frozen=True)
class LoadedProject:
    config: Config
    resolved: ResolvedConfig
    entrypoints: list[Blueprint]


def require_blueprint_config(config: Config, *, command: str) -> BlueprintConfig:
    if config.blueprint is None:
        raise ValueError(f"[{command}] 配置中未找到blueprint段落")
    return config.blueprint


def load_project(config_path: str | Path | None, *, command: str = "load_project") -> LoadedProject:
    resolved = resolve_config(config_path)
    blueprint = require_blueprint_config(resolved.raw, command=command)
    entrypoints = load_entrypoints(blueprint.entrypoints, resolved.entrypoint_root)
    return LoadedProject(
        config=resolved.raw,
        resolved=resolved,
        entrypoints=entrypoints,
    )


def build_entrypoints(entrypoints: list[Blueprint]) -> None:
    for blueprint in entrypoints:
        blueprint.build()
