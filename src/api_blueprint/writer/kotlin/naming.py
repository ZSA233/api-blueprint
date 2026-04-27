from __future__ import annotations

import re


KOTLIN_KEYWORDS = frozenset(
    {
        "as",
        "break",
        "class",
        "continue",
        "do",
        "else",
        "false",
        "for",
        "fun",
        "if",
        "in",
        "interface",
        "is",
        "null",
        "object",
        "package",
        "return",
        "super",
        "this",
        "throw",
        "true",
        "try",
        "typealias",
        "typeof",
        "val",
        "var",
        "when",
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


def to_kotlin_type_name(value: str, *, fallback: str = "GeneratedType") -> str:
    tokens = split_tokens(value)
    result = "".join(cap_token(token) for token in tokens)
    if not result:
        result = fallback
    if not result[0].isalpha():
        result = fallback + result
    return result


def to_kotlin_property_name(value: str, *, fallback: str = "value") -> str:
    type_name = to_kotlin_type_name(value, fallback=fallback.capitalize())
    result = type_name[:1].lower() + type_name[1:]
    if result in KOTLIN_KEYWORDS:
        return f"`{result}`"
    return result


def to_package_path(package: str) -> str:
    return package.replace(".", "/")

