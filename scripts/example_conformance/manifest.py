from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClientCapability:
    name: str
    command_label: str
    supports_rpc: bool
    supports_binary: bool
    supports_form: bool
    supports_typed_error: bool
    supports_sse: bool
    supports_websocket: bool
    connection_policy: str = "native"


@dataclass(frozen=True)
class ServerCapability:
    name: str
    command_label: str
    enabled: bool
    planned: bool


def client_manifest() -> dict[str, ClientCapability]:
    return {
        "go": ClientCapability(
            name="go",
            command_label="Go",
            supports_rpc=True,
            supports_binary=True,
            supports_form=True,
            supports_typed_error=True,
            supports_sse=False,
            supports_websocket=False,
            connection_policy="raw-probe",
        ),
        "typescript": ClientCapability(
            name="typescript",
            command_label="TypeScript",
            supports_rpc=True,
            supports_binary=True,
            supports_form=True,
            supports_typed_error=True,
            supports_sse=True,
            supports_websocket=True,
        ),
        "kotlin": ClientCapability(
            name="kotlin",
            command_label="Kotlin",
            supports_rpc=True,
            supports_binary=True,
            supports_form=True,
            supports_typed_error=True,
            supports_sse=True,
            supports_websocket=True,
        ),
        "flutter": ClientCapability(
            name="flutter",
            command_label="Flutter",
            supports_rpc=True,
            supports_binary=True,
            supports_form=True,
            supports_typed_error=True,
            supports_sse=True,
            supports_websocket=True,
        ),
    }


def server_manifest() -> dict[str, ServerCapability]:
    return {
        "go": ServerCapability("go", "Go HTTP", enabled=True, planned=True),
        "java": ServerCapability("java", "Java Spring", enabled=False, planned=True),
        "kotlin": ServerCapability("kotlin", "Kotlin Ktor", enabled=False, planned=True),
        "python": ServerCapability("python", "Python FastAPI", enabled=False, planned=True),
    }


def parse_csv_filter(raw: str | None, available: set[str], *, label: str) -> tuple[str, ...]:
    if raw is None or raw.strip() == "":
        return tuple(sorted(available))
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    unknown = [value for value in values if value not in available]
    if unknown:
        raise ValueError(f"unknown {label}: {', '.join(unknown)}")
    return values


def require_enabled_server(server: str) -> ServerCapability:
    servers = server_manifest()
    if server not in servers:
        raise ValueError(f"unknown conformance server: {server}")
    selected = servers[server]
    if not selected.enabled:
        raise ValueError(f"server {server} is planned but not enabled")
    return selected
