from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from api_blueprint.config import Config, ResolvedConfig, resolve_config
from api_blueprint.engine import Blueprint

from .entrypoints import load_entrypoints


@dataclass(frozen=True)
class LoadedProject:
    config: Config
    resolved: ResolvedConfig
    entrypoints: list[Blueprint]


def load_project(config_path: str | Path | None) -> LoadedProject:
    resolved = resolve_config(config_path)
    entrypoints = load_entrypoints(resolved.raw.blueprint.entrypoints, resolved.entrypoint_root)
    return LoadedProject(
        config=resolved.raw,
        resolved=resolved,
        entrypoints=entrypoints,
    )


def build_entrypoints(entrypoints: list[Blueprint]) -> None:
    for blueprint in entrypoints:
        blueprint.build()
