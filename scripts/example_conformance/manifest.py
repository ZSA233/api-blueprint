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
    supports_media: bool = False


@dataclass(frozen=True)
class ServerCapability:
    name: str
    command_label: str
    enabled: bool
    planned: bool
    supports_rpc: bool
    supports_binary: bool
    supports_form: bool
    supports_typed_error: bool
    supports_sse: bool
    supports_websocket: bool
    supports_naming: bool
    supports_media: bool = False


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
            supports_media=True,
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
            supports_media=True,
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
            supports_media=True,
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
            supports_media=True,
        ),
        "swift": ClientCapability(
            name="swift",
            command_label="Swift",
            supports_rpc=True,
            supports_binary=True,
            supports_form=True,
            supports_typed_error=True,
            supports_sse=False,
            supports_websocket=False,
            connection_policy="protocol-bridge",
            supports_media=True,
        ),
        "java": ClientCapability(
            name="java",
            command_label="Java",
            supports_rpc=True,
            supports_binary=True,
            supports_form=True,
            supports_typed_error=True,
            supports_sse=True,
            supports_websocket=True,
            connection_policy="unsupported-contract",
            supports_media=True,
        ),
        "python": ClientCapability(
            name="python",
            command_label="Python",
            supports_rpc=True,
            supports_binary=True,
            supports_form=True,
            supports_typed_error=True,
            supports_sse=True,
            supports_websocket=True,
            connection_policy="unsupported-contract",
            supports_media=True,
        ),
    }


def server_manifest() -> dict[str, ServerCapability]:
    return {
        "go": ServerCapability(
            "go",
            "Go HTTP",
            enabled=True,
            planned=True,
            supports_rpc=True,
            supports_binary=True,
            supports_form=True,
            supports_typed_error=True,
            supports_sse=True,
            supports_websocket=True,
            supports_naming=True,
            supports_media=True,
        ),
        "java": ServerCapability(
            "java",
            "Java Spring",
            enabled=True,
            planned=True,
            supports_rpc=True,
            supports_binary=True,
            supports_form=True,
            supports_typed_error=True,
            supports_sse=True,
            supports_websocket=True,
            supports_naming=True,
            supports_media=True,
        ),
        "kotlin": ServerCapability(
            "kotlin",
            "Kotlin Ktor",
            enabled=True,
            planned=True,
            supports_rpc=True,
            supports_binary=True,
            supports_form=True,
            supports_typed_error=True,
            supports_sse=True,
            supports_websocket=True,
            supports_naming=True,
            supports_media=True,
        ),
        "python": ServerCapability(
            "python",
            "Python FastAPI",
            enabled=True,
            planned=True,
            supports_rpc=True,
            supports_binary=True,
            supports_form=True,
            supports_typed_error=True,
            supports_sse=True,
            supports_websocket=True,
            supports_naming=True,
            supports_media=True,
        ),
    }


def parse_csv_filter(raw: str | None, available: set[str], *, label: str) -> tuple[str, ...]:
    if raw is None or raw.strip() == "":
        return tuple(sorted(available))
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    if "all" in values:
        return tuple(sorted(available))
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
