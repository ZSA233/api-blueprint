from __future__ import annotations

import re


DART_KEYWORDS = frozenset(
    {
        "abstract",
        "as",
        "assert",
        "async",
        "await",
        "base",
        "break",
        "case",
        "catch",
        "class",
        "const",
        "continue",
        "covariant",
        "default",
        "deferred",
        "do",
        "dynamic",
        "else",
        "enum",
        "export",
        "extends",
        "extension",
        "external",
        "factory",
        "false",
        "final",
        "finally",
        "for",
        "function",
        "get",
        "hide",
        "if",
        "implements",
        "import",
        "in",
        "interface",
        "is",
        "late",
        "library",
        "mixin",
        "new",
        "null",
        "of",
        "on",
        "operator",
        "part",
        "required",
        "rethrow",
        "return",
        "sealed",
        "set",
        "show",
        "static",
        "super",
        "switch",
        "sync",
        "this",
        "throw",
        "true",
        "try",
        "type",
        "typedef",
        "var",
        "void",
        "when",
        "while",
        "with",
        "yield",
    }
)


def split_tokens(value: str) -> list[str]:
    tokens: list[str] = []
    for segment in value.split("/"):
        if not segment:
            continue
        tokens.extend(token for token in re.split(r"[^0-9A-Za-z]+", segment) if token)
    return tokens


def cap_token(token: str) -> str:
    if not token:
        return ""
    if token.isupper():
        return token[:1].upper() + token[1:].lower()
    return token[:1].upper() + token[1:]


def to_dart_type_name(value: str, *, fallback: str = "GeneratedType") -> str:
    tokens = split_tokens(value)
    result = "".join(cap_token(token) for token in tokens)
    if not result:
        result = fallback
    if not result[0].isalpha():
        result = fallback + result
    return result


def to_dart_identifier(value: str, *, fallback: str = "value") -> str:
    type_name = to_dart_type_name(value, fallback=fallback.capitalize())
    result = type_name[:1].lower() + type_name[1:]
    if result in DART_KEYWORDS:
        return f"{result}_"
    return result


def to_dart_file_stem(value: str, *, fallback: str = "root") -> str:
    tokens = split_tokens(value)
    result = "_".join(token.lower() for token in tokens)
    if not result:
        result = fallback
    if not result[0].isalpha():
        result = f"{fallback}_{result}"
    if result in DART_KEYWORDS:
        return f"{result}_"
    return result


def to_dart_path(value: str, *, fallback: str = "root") -> str:
    parts = [to_dart_file_stem(part, fallback=fallback) for part in value.strip("/").split("/") if part]
    return "/".join(parts or [fallback])


def to_dart_package_name(value: str) -> str:
    parts = [part for part in re.split(r"[^0-9A-Za-z_]+", value.strip()) if part]
    rendered = "_".join(part.lower() for part in parts) or "api_blueprint_generated"
    if not rendered[0].isalpha():
        rendered = f"api_{rendered}"
    return rendered
