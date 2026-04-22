from __future__ import annotations

import json
import re


def cap_token(token: str) -> str:
    if not token:
        return ""
    if token.isupper():
        return token[:1].upper() + token[1:].lower()
    return token[:1].upper() + token[1:]


def to_ts_name(name: str, invalid_prefix: str = "Func") -> str:
    if not name:
        return "AnonType"
    if re.fullmatch(r"[A-Z][A-Za-z0-9]*", name):
        return name

    tokens: list[str] = []
    for segment in name.split("/"):
        if not segment:
            continue
        tokens.extend(token for token in re.split(r"[^0-9A-Za-z]+", segment) if token)

    result = "".join(cap_token(token) for token in tokens)
    if not result:
        return "AnonType"
    if not result[0].isalpha():
        result = invalid_prefix + result
    return result


def to_ts_identifier(name: str) -> str:
    if not name:
        return '"_"'
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        return name
    return json.dumps(name)


def to_camel(name: str) -> str:
    if not name:
        return name
    return name[0].lower() + name[1:]
