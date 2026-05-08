from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

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


AliasTargetKind = Literal[
    "go-server",
    "go-client",
    "typescript-client",
    "kotlin-client",
    "python-server",
    "python-client",
    "http-transport",
    "wails-transport",
    "grpc-proto",
    "grpc-go",
    "grpc-python",
]
AliasTable = tuple[str, str]
TargetPayload = dict[str, Any]


ALIAS_TARGET_KINDS: dict[AliasTable, AliasTargetKind] = {
    ("go", "server"): "go-server",
    ("go", "client"): "go-client",
    ("typescript", "client"): "typescript-client",
    ("kotlin", "client"): "kotlin-client",
    ("python", "server"): "python-server",
    ("python", "client"): "python-client",
    ("transport", "http"): "http-transport",
    ("transport", "wails"): "wails-transport",
    ("grpc", "proto"): "grpc-proto",
    ("grpc", "go"): "grpc-go",
    ("grpc", "python"): "grpc-python",
}
ALIAS_NAMESPACES = frozenset(namespace for namespace, _table in ALIAS_TARGET_KINDS)


def normalize_target_aliases(payload: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    alias_targets: list[TargetPayload] = []

    for key, value in payload.items():
        if key not in ALIAS_NAMESPACES:
            normalized[key] = value
            continue
        if not isinstance(value, dict):
            raise ValueError(f"config alias namespace [{key}] must contain target alias tables")
        alias_targets.extend(_normalize_alias_namespace(key, value))

    if alias_targets:
        targets = normalized.setdefault("targets", [])
        if not isinstance(targets, list):
            raise ValueError("config field [[targets]] must be an array table")
        targets.extend(alias_targets)
    return normalized


def _normalize_alias_namespace(namespace: str, tables: dict[str, Any]) -> list[TargetPayload]:
    targets: list[TargetPayload] = []
    for table, items in tables.items():
        alias_table = (namespace, table)
        kind = ALIAS_TARGET_KINDS.get(alias_table)
        label = f"[[{namespace}.{table}]]"
        if kind is None:
            raise ValueError(f"unsupported config alias table {label}")
        if not isinstance(items, list):
            raise ValueError(f"config alias table {label} must be an array table")
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"config alias table {label} entries must be tables")
            targets.append(_normalize_alias_target(label, kind, item))
    return targets


def _normalize_alias_target(label: str, kind: AliasTargetKind, item: TargetPayload) -> TargetPayload:
    if "kind" in item:
        raise ValueError(f"config alias table {label} must not include kind; it is inferred from the table name")
    target = dict(item)
    _normalize_contextual_module(label, kind, target)
    target["kind"] = kind
    return target


def _normalize_contextual_module(label: str, kind: AliasTargetKind, target: TargetPayload) -> None:
    if kind in {"python-server", "python-client", "grpc-python"}:
        _move_matching_alias_field(label, target, source="module", destination="python_package_root")
    if kind == "kotlin-client":
        _move_matching_alias_field(label, target, source="module", destination="package")


def _move_matching_alias_field(label: str, target: TargetPayload, *, source: str, destination: str) -> None:
    source_value = target.get(source)
    destination_value = target.get(destination)
    if source_value is None:
        return
    if destination_value is not None and source_value != destination_value:
        raise ValueError(f"config alias table {label} {source} and {destination} must match when both are set")
    target[destination] = source_value
    del target[source]


def load_config(path: str | Path | None):
    from api_blueprint.config.models import Config

    normalized = normalize_config_path(path)
    payload = normalize_target_aliases(read_toml(normalized))
    return Config(**payload)
