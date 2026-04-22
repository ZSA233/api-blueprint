from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


WriterFactory = Callable[..., Any]


@dataclass(frozen=True)
class GeneratorTargetSpec:
    name: str
    implemented: bool
    writer_factory: WriterFactory | None = None
    description: str = ""


_REGISTRY: dict[str, GeneratorTargetSpec] = {}


def register_target(spec: GeneratorTargetSpec) -> None:
    _REGISTRY[spec.name] = spec


def register_placeholder_target(name: str, description: str) -> None:
    if name in _REGISTRY:
        return
    register_target(
        GeneratorTargetSpec(
            name=name,
            implemented=False,
            writer_factory=None,
            description=description,
        )
    )


def get_target(name: str) -> GeneratorTargetSpec:
    return _REGISTRY[name]


def iter_targets() -> tuple[GeneratorTargetSpec, ...]:
    return tuple(_REGISTRY.values())


def ensure_default_targets() -> None:
    register_placeholder_target("kotlin", "Reserved internal target for future Android Kotlin generation.")
    register_placeholder_target("java", "Reserved internal target for future Android Java generation.")
    register_placeholder_target("grpc", "Reserved internal target for future gRPC wrapper generation.")
