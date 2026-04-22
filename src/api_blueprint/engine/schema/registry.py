from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .modeling import Model


_ERROR_MODELS: dict[str, type["Model"]] = {}
_NAMED_MODELS: dict[str, type["Model"]] = {}


def register_model(name: str, cls: type["Model"], *, has_error: bool) -> None:
    _NAMED_MODELS[name] = cls
    if has_error:
        _ERROR_MODELS[name] = cls


def iter_error_models() -> tuple[tuple[str, type["Model"]], ...]:
    return tuple(_ERROR_MODELS.items())


def get_named_model(name: str) -> type["Model"] | None:
    return _NAMED_MODELS.get(name)
