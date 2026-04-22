from __future__ import annotations

import importlib
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from api_blueprint.engine import Blueprint
from api_blueprint.engine.runtime import reset_response_wrapper_cache, reset_shared_app
from api_blueprint.engine.schema import reset_pydantic_model_cache


@contextmanager
def import_path_scope(*paths: Path | str | None) -> Generator[None, None, None]:
    added: list[str] = []
    try:
        for path in paths:
            if path is None:
                continue
            value = str(Path(path).resolve())
            if value not in sys.path:
                sys.path.insert(0, value)
                added.append(value)
        yield
    finally:
        for path in reversed(added):
            if path in sys.path:
                sys.path.remove(path)


def load_entrypoints(specs: list[str] | None, relative_path: Path | None = None) -> list[Blueprint]:
    if not specs:
        return []

    reset_shared_app()
    reset_response_wrapper_cache()
    reset_pydantic_model_cache()

    entrypoints: list[Blueprint] = []
    with import_path_scope(Path.cwd(), relative_path):
        for spec in specs:
            if ":" not in spec:
                raise Exception(f"Invalid entrypoint spec: {spec!r}, 必须形如 'module.path:attribute'")
            module_path, attr_name = spec.split(":", 1)
            try:
                importlib.invalidate_caches()
                unload_module_tree(module_path)
                module: types.ModuleType = importlib.import_module(module_path)
            except ImportError as exc:
                raise Exception(f"无法导入模块 '{module_path}': {exc}") from exc

            if attr_name == "*":
                for value in module.__dict__.values():
                    if isinstance(value, Blueprint):
                        entrypoints.append(value)
                continue

            if not hasattr(module, attr_name):
                raise Exception(f"模块 '{module_path}' 中不存在属性 '{attr_name}'")
            entrypoints.append(getattr(module, attr_name))

    return entrypoints


def unload_module_tree(module_path: str) -> None:
    root = module_path.split(".", 1)[0]
    for name in list(sys.modules):
        if (
            name == module_path
            or name.startswith(f"{module_path}.")
            or name == root
            or name.startswith(f"{root}.")
        ):
            sys.modules.pop(name)
