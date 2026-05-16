from __future__ import annotations

import re


GO_KEYWORDS = frozenset(
    {
        "break",
        "default",
        "func",
        "interface",
        "select",
        "case",
        "defer",
        "go",
        "map",
        "struct",
        "chan",
        "else",
        "goto",
        "package",
        "switch",
        "const",
        "fallthrough",
        "if",
        "range",
        "type",
        "continue",
        "for",
        "import",
        "return",
        "var",
    }
)


def to_go_package_name(value: str, *, fallback: str = "root") -> str:
    package = re.sub(r"[^0-9A-Za-z_]+", "_", value.strip("/").lower()).strip("_")
    if not package:
        package = fallback
    if package[:1].isdigit():
        package = f"p_{package}"
    if package in GO_KEYWORDS:
        package = f"{package}_pkg"
    return package


def to_go_package_path(value: str, *, fallback: str = "root") -> str:
    parts = [to_go_package_name(part, fallback=fallback) for part in value.strip("/").split("/") if part]
    return "_".join(parts) if parts else to_go_package_name("", fallback=fallback)


def to_go_exported_name(value: str, *, fallback: str = "Value") -> str:
    tokens = [token for token in re.split(r"[^0-9A-Za-z]+", value.strip("/")) if token]
    result = "".join(token[:1].upper() + token[1:] for token in tokens)
    if not result:
        result = fallback
    if result[:1].isdigit():
        result = f"{fallback}{result}"
    return result
