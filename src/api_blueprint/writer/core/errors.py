from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class ErrorToastSpec:
    key: str
    default: str
    level: str


@dataclass(frozen=True)
class ErrorCatalogEntry:
    id: str
    group: str
    key: str
    code: int
    message: str
    toast: ErrorToastSpec

    @property
    def group_symbol(self) -> str:
        return _pascal_identifier(self.group, default="ApiErrors")

    @property
    def key_symbol(self) -> str:
        return _upper_identifier(self.key, default="CODE")

    @property
    def go_const_symbol(self) -> str:
        return f"{self.group_symbol}{_pascal_identifier(self.key, default='Code')}"


@dataclass(frozen=True)
class ErrorCatalogGroup:
    symbol: str
    name: str
    entries: tuple[ErrorCatalogEntry, ...]


def error_catalog_from_manifest(
    manifest: Mapping[str, Any],
    *,
    route_ids: Iterable[str] | None = None,
    error_ids: Iterable[str] | None = None,
    root: str | None = None,
) -> tuple[ErrorCatalogEntry, ...]:
    raw_errors = manifest.get("errors")
    if not isinstance(raw_errors, list):
        return ()
    selected_error_ids = _selected_error_ids(manifest, route_ids=route_ids, error_ids=error_ids, root=root)
    entries: list[ErrorCatalogEntry] = []
    for raw_error in raw_errors:
        if not isinstance(raw_error, Mapping):
            continue
        raw_id = str(raw_error.get("id") or "")
        if selected_error_ids is not None and raw_id not in selected_error_ids:
            continue
        raw_toast = raw_error.get("toast")
        entries.append(
            ErrorCatalogEntry(
                id=raw_id,
                group=str(raw_error.get("group") or "ApiErrors"),
                key=str(raw_error.get("key") or "CODE"),
                code=int(raw_error.get("code") or 0),
                message=str(raw_error.get("message") or ""),
                toast=_toast_from_manifest(raw_toast, fallback_key=raw_id, fallback_default=str(raw_error.get("message") or "")),
            )
        )
    return tuple(entries)


def group_error_catalog(entries: tuple[ErrorCatalogEntry, ...]) -> tuple[ErrorCatalogGroup, ...]:
    grouped: "OrderedDict[str, list[ErrorCatalogEntry]]" = OrderedDict()
    names: dict[str, str] = {}
    for entry in entries:
        grouped.setdefault(entry.group, []).append(entry)
        names.setdefault(entry.group, entry.group_symbol)
    return tuple(
        ErrorCatalogGroup(symbol=names[group], name=group, entries=tuple(group_entries))
        for group, group_entries in grouped.items()
    )


def _pascal_identifier(value: str, *, default: str) -> str:
    parts = [part for part in re.split(r"[^0-9A-Za-z]+", value) if part]
    text = "".join(part[:1].upper() + (part[1:].lower() if part.isupper() else part[1:]) for part in parts) or default
    if not text[0].isalpha():
        text = f"{default}{text}"
    return text


def _upper_identifier(value: str, *, default: str) -> str:
    text = re.sub(r"[^0-9A-Za-z]+", "_", value).strip("_").upper() or default
    if not text[0].isalpha() and text[0] != "_":
        text = f"{default}_{text}"
    return text


def _selected_error_ids(
    manifest: Mapping[str, Any],
    *,
    route_ids: Iterable[str] | None,
    error_ids: Iterable[str] | None,
    root: str | None,
) -> set[str] | None:
    if error_ids is not None:
        return {str(error_id) for error_id in error_ids}
    route_filter = {str(route_id) for route_id in route_ids} if route_ids is not None else None
    root_filter = root.strip("/") if isinstance(root, str) and root.strip("/") else None
    if route_filter is None and root_filter is None:
        return None

    selected: set[str] = set()
    raw_routes = manifest.get("routes")
    if not isinstance(raw_routes, list):
        return selected
    for raw_route in raw_routes:
        if not isinstance(raw_route, Mapping):
            continue
        route_id = str(raw_route.get("id") or "")
        if route_filter is not None and route_id not in route_filter:
            continue
        if root_filter is not None and route_id.split(".", 1)[0] != root_filter:
            continue
        raw_route_errors = raw_route.get("errors")
        if isinstance(raw_route_errors, list):
            selected.update(str(error_id) for error_id in raw_route_errors)
    return selected


def _toast_from_manifest(value: object, *, fallback_key: str, fallback_default: str) -> ErrorToastSpec:
    if not isinstance(value, Mapping):
        return ErrorToastSpec(key=fallback_key, default=fallback_default, level="error")
    return ErrorToastSpec(
        key=str(value.get("key") or fallback_key),
        default=str(value.get("default") or fallback_default),
        level=str(value.get("level") or "error"),
    )
