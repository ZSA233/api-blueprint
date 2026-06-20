from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RoutePublicNames:
    operation: str
    path: str
    query: str
    json: str
    form: str
    headers: str
    binary: str
    open: str
    close: str
    response: str

    @classmethod
    def from_operation(cls, operation: object, *, fallback: str = "Call") -> "RoutePublicNames":
        name = public_type_name(str(operation or ""), fallback=fallback)
        return cls(
            operation=name,
            path=f"{name}Path",
            query=f"{name}Query",
            json=f"{name}JSON",
            form=f"{name}Form",
            headers=f"{name}Headers",
            binary=f"{name}Binary",
            open=f"{name}Open",
            close=f"{name}Close",
            response=f"{name}Response",
        )


_GO_INITIALISMS = {
    "api": "API",
    "ascii": "ASCII",
    "cpu": "CPU",
    "css": "CSS",
    "dns": "DNS",
    "eof": "EOF",
    "guid": "GUID",
    "html": "HTML",
    "http": "HTTP",
    "https": "HTTPS",
    "id": "ID",
    "ids": "IDs",
    "ip": "IP",
    "json": "JSON",
    "kv": "KV",
    "qps": "QPS",
    "ram": "RAM",
    "rpc": "RPC",
    "sql": "SQL",
    "ssh": "SSH",
    "tcp": "TCP",
    "tls": "TLS",
    "ttl": "TTL",
    "udp": "UDP",
    "ui": "UI",
    "uid": "UID",
    "uri": "URI",
    "url": "URL",
    "utf8": "UTF8",
    "uuid": "UUID",
    "vm": "VM",
    "ws": "WS",
    "xml": "XML",
}


def public_type_name(value: str, *, fallback: str = "Call") -> str:
    parts = _identifier_parts(value)
    text = "".join(_pascalize(part) for part in parts) or fallback
    if text[:1].isdigit():
        text = f"{fallback}{text}"
    return text


def go_exported_field_name(value: str, *, fallback: str = "Value") -> str:
    parts = _identifier_parts(value)
    text = "".join(_go_part(part) for part in parts) or fallback
    if text[:1].isdigit():
        text = f"{fallback}{text}"
    return text


def _identifier_parts(value: str) -> list[str]:
    return [part for part in re.split(r"[^0-9A-Za-z_]+|_", value) if part]


def _pascalize(value: str) -> str:
    return value[:1].upper() + value[1:] if value else value


def _go_part(value: str) -> str:
    lower = value.lower()
    if lower in _GO_INITIALISMS:
        return _GO_INITIALISMS[lower]
    return _pascalize(value)
