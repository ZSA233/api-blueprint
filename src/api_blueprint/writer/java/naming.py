from __future__ import annotations

import re


JAVA_KEYWORDS = frozenset(
    {
        "abstract",
        "assert",
        "boolean",
        "break",
        "byte",
        "case",
        "catch",
        "char",
        "class",
        "const",
        "continue",
        "default",
        "do",
        "double",
        "else",
        "enum",
        "extends",
        "final",
        "finally",
        "float",
        "for",
        "goto",
        "if",
        "implements",
        "import",
        "instanceof",
        "int",
        "interface",
        "long",
        "native",
        "new",
        "package",
        "private",
        "protected",
        "public",
        "return",
        "short",
        "static",
        "strictfp",
        "super",
        "switch",
        "synchronized",
        "this",
        "throw",
        "throws",
        "transient",
        "try",
        "void",
        "volatile",
        "while",
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


def to_java_type_name(value: str, *, fallback: str = "GeneratedType") -> str:
    tokens = split_tokens(value)
    result = "".join(cap_token(token) for token in tokens)
    if not result:
        result = fallback
    if not result[0].isalpha():
        result = fallback + result
    if result in JAVA_KEYWORDS:
        result += "Type"
    return result


def to_java_member_name(value: str, *, fallback: str = "value") -> str:
    type_name = to_java_type_name(value, fallback=fallback.capitalize())
    result = type_name[:1].lower() + type_name[1:]
    if result in JAVA_KEYWORDS:
        result += "Value"
    return result


def to_java_constant_name(value: str, *, fallback: str = "VALUE") -> str:
    tokens = split_tokens(value)
    if not tokens:
        return fallback
    result = "_".join(token.upper() for token in tokens)
    if result[:1].isdigit():
        result = f"{fallback}_{result}"
    if result.lower() in JAVA_KEYWORDS:
        result += "_VALUE"
    return result


def to_java_package_component(value: str, *, fallback: str = "root") -> str:
    tokens = split_tokens(value)
    result = "".join(token.lower() for token in tokens)
    if not result:
        result = fallback
    if not result[0].isalpha():
        result = f"{fallback}{result}"
    if result in JAVA_KEYWORDS:
        result += "_"
    return result


def to_java_package_path(value: str, *, fallback: str = "root") -> str:
    parts = [to_java_package_component(part, fallback=fallback) for part in value.strip("/").split("/") if part]
    return "/".join(parts or [fallback])


def to_java_package_suffix(value: str, *, fallback: str = "root") -> str:
    return to_java_package_path(value, fallback=fallback).replace("/", ".")


def to_package_path(package: str) -> str:
    return package.replace(".", "/")
