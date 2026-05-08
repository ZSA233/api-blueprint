from __future__ import annotations

import keyword
import re


def to_package_segments(package_root: str | None) -> tuple[str, ...]:
    raw = package_root or "api_blueprint_generated"
    return tuple(_identifier(segment, default="generated") for segment in raw.replace("/", ".").split(".") if segment)


def to_path_segments(path: str, *, default: str) -> tuple[str, ...]:
    stripped = path.strip("/")
    if not stripped:
        return (_identifier(default, default=default),)
    return tuple(_identifier(segment, default=default) for segment in stripped.split("/") if segment)


def to_py_identifier(value: str, *, default: str) -> str:
    return _identifier(value, default=default)


def to_py_class_name(value: str, *, default: str) -> str:
    candidate = re.sub(r"[^0-9A-Za-z]+", " ", value).strip()
    if not candidate:
        candidate = default
    name = "".join(part[:1].upper() + part[1:] for part in candidate.split())
    if not name:
        name = default
    if name[0].isdigit():
        name = f"_{name}"
    return name


def _identifier(value: str, *, default: str) -> str:
    value = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    normalized = re.sub(r"[^0-9A-Za-z_]+", "_", value).strip("_").lower()
    normalized = normalized or default
    if normalized[0].isdigit():
        normalized = f"_{normalized}"
    if keyword.iskeyword(normalized):
        normalized = f"{normalized}_"
    return normalized
