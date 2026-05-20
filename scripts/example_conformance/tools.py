from __future__ import annotations

import shutil

from scripts import example_validation


def missing_tools_for_clients(clients: tuple[str, ...]) -> tuple[str, ...]:
    requirements: dict[str, tuple[str, ...]] = {
        "go": ("go",),
        "typescript": ("node", "tsc"),
        "kotlin": (),
        "flutter": ("dart",),
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
    return tuple(missing)


def missing_tools_for_targets(server: str, clients: tuple[str, ...]) -> tuple[str, ...]:
    missing = list(missing_tools_for_clients(clients))
    if server == "go" and shutil.which("go") is None:
        server_entry = "go: required for go conformance server"
        if server_entry not in missing:
            missing.insert(0, server_entry)
    return tuple(missing)


def ensure_tools_for_clients(clients: tuple[str, ...]) -> None:
    missing = missing_tools_for_clients(clients)
    if missing:
        raise RuntimeError("example conformance requires additional tooling:\n" + "\n".join(missing))


def ensure_tools_for_targets(server: str, clients: tuple[str, ...]) -> None:
    missing = missing_tools_for_targets(server, clients)
    if missing:
        raise RuntimeError("example conformance requires additional tooling:\n" + "\n".join(missing))
