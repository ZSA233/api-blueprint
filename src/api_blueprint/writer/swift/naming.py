from __future__ import annotations

import re


SWIFT_KEYWORDS = frozenset(
    {
        "Any",
        "Self",
        "Type",
        "actor",
        "as",
        "associatedtype",
        "async",
        "await",
        "break",
        "case",
        "catch",
        "class",
        "continue",
        "default",
        "defer",
        "deinit",
        "do",
        "else",
        "enum",
        "extension",
        "fallthrough",
        "false",
        "fileprivate",
        "for",
        "func",
        "guard",
        "if",
        "import",
        "in",
        "init",
        "inout",
        "internal",
        "is",
        "let",
        "nil",
        "open",
        "operator",
        "private",
        "protocol",
        "public",
        "repeat",
        "return",
        "self",
        "static",
        "struct",
        "subscript",
        "super",
        "switch",
        "throw",
        "throws",
        "true",
        "try",
        "typealias",
        "var",
        "where",
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
    if token.lower() == "api":
        return "API"
    if token.isupper():
        return token[:1].upper() + token[1:].lower()
    return token[:1].upper() + token[1:]


def to_swift_type_name(value: str, *, fallback: str = "GeneratedType") -> str:
    tokens = split_tokens(value)
    result = "".join(cap_token(token) for token in tokens)
    if not result:
        result = fallback
    if not result[0].isalpha():
        result = fallback + result
    if result in SWIFT_KEYWORDS:
        return f"{result}_"
    return result


def to_swift_identifier(value: str, *, fallback: str = "value") -> str:
    type_name = to_swift_type_name(value, fallback=fallback.capitalize())
    if type_name == "API":
        result = "api"
    elif type_name.startswith("API") and len(type_name) > 3 and type_name[3].isupper():
        result = "api" + type_name[3:]
    else:
        result = type_name[:1].lower() + type_name[1:]
    if result in SWIFT_KEYWORDS:
        return f"{result}_"
    return result


def to_swift_path(value: str, *, fallback: str = "Root") -> str:
    parts = [to_swift_type_name(part, fallback=fallback) for part in value.strip("/").split("/") if part]
    return "/".join(parts or [fallback])


def to_swift_module_name(value: str) -> str:
    return to_swift_type_name(value, fallback="ApiBlueprintGenerated")
