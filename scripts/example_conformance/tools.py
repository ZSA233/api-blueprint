from __future__ import annotations

import importlib.util
import shutil

from scripts import example_validation


def missing_tools_for_clients(clients: tuple[str, ...]) -> tuple[str, ...]:
    requirements: dict[str, tuple[str, ...]] = {
        "go": ("go",),
        "typescript": ("node", "tsc"),
        "kotlin": (),
        "flutter": ("dart",),
        "swift": (),
        "java": (),
        "python": (),
    }
    missing: list[str] = []
    for client in clients:
        for binary in requirements.get(client, ()):
            if shutil.which(binary) is None:
                missing.append(f"{binary}: required for {client} conformance")
    if "kotlin" in clients and example_validation.resolve_gradle_bin() is None:
        missing.append(
            f"gradle: required for kotlin conformance; set {example_validation.GRADLE_BIN_ENV} if needed"
        )
    if "java" in clients and example_validation.resolve_gradle_bin() is None:
        missing.append(
            f"gradle: required for java conformance; set {example_validation.GRADLE_BIN_ENV} if needed"
        )
    if "swift" in clients and example_validation.resolve_swift_bin() is None:
        missing.append(
            f"swift: required for swift conformance; set {example_validation.SWIFT_BIN_ENV} if needed"
        )
    return tuple(missing)


def missing_tools_for_targets(servers: str | tuple[str, ...], clients: tuple[str, ...]) -> tuple[str, ...]:
    server_names = (servers,) if isinstance(servers, str) else servers
    missing = list(missing_tools_for_clients(clients))
    if "go" in server_names and shutil.which("go") is None:
        server_entry = "go: required for go conformance server"
        if server_entry not in missing:
            missing.insert(0, server_entry)
    if any(server in server_names for server in ("java", "kotlin")) and example_validation.resolve_gradle_bin() is None:
        missing.append(
            f"gradle: required for java/kotlin conformance server; set {example_validation.GRADLE_BIN_ENV} if needed"
        )
    if "python" in server_names and importlib.util.find_spec("websockets") is None:
        missing.append("websockets: required for python conformance server WebSocket support")
    return tuple(missing)


def ensure_tools_for_clients(clients: tuple[str, ...]) -> None:
    missing = missing_tools_for_clients(clients)
    if missing:
        raise RuntimeError("example conformance requires additional tooling:\n" + "\n".join(missing))


def ensure_tools_for_targets(servers: str | tuple[str, ...], clients: tuple[str, ...]) -> None:
    missing = missing_tools_for_targets(servers, clients)
    if missing:
        raise RuntimeError("example conformance requires additional tooling:\n" + "\n".join(missing))
