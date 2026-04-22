from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


def normalize_config_path(path: str | Path | None) -> Path:
    target = Path(path or "./api-blueprint.toml").resolve()
    if target.is_dir():
        target /= "api-blueprint.toml"
    return target


def read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as file:
        return tomllib.load(file)


def load_config(path: str | Path | None):
    from api_blueprint.config.models import Config

    normalized = normalize_config_path(path)
    payload = read_toml(normalized)
    return Config(**payload)
