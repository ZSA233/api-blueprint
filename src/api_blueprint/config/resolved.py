from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from api_blueprint.config.loader import normalize_config_path
from api_blueprint.config.models import Config


@dataclass(frozen=True)
class ResolvedTargetConfig:
    output: Path | None
    upstream: str | None = None
    module: str | None = None
    base_url: str | None = None


@dataclass(frozen=True)
class ResolvedConfig:
    path: Path
    project_root: Path
    entrypoint_root: Path
    raw: Config
    golang: ResolvedTargetConfig
    typescript: ResolvedTargetConfig | None


def resolve_output_path(config_path: Path, output: str | None) -> Path | None:
    if output is None:
        return None

    target = Path(output)
    if not target.is_absolute():
        target = (config_path.parent / target).resolve()
    return target


def resolve_config(path: str | Path | None) -> ResolvedConfig:
    normalized = normalize_config_path(path)
    raw = Config.load(normalized)

    tsconf = raw.typescript
    return ResolvedConfig(
        path=normalized,
        project_root=normalized.parent,
        entrypoint_root=normalized.parent,
        raw=raw,
        golang=ResolvedTargetConfig(
            output=resolve_output_path(normalized, raw.golang.codegen_output),
            upstream=raw.golang.upstream,
            module=raw.golang.module,
        ),
        typescript=None
        if tsconf is None
        else ResolvedTargetConfig(
            output=resolve_output_path(normalized, tsconf.codegen_output or "typescript"),
            upstream=tsconf.upstream,
            base_url=tsconf.base_url,
        ),
    )
