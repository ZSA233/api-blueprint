import importlib
from api_blueprint.engine import Blueprint
from pathlib import Path
import typing
import types
import importlib
import sys
import os


def load_entrypoints(specs: typing.List[str], relative_path: typing.Optional[Path] = None) -> typing.List[Blueprint]:
    entrypoints: typing.List[Blueprint] = []
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.append(cwd)
    if relative_path is not None and (relpath := relative_path.resolve()) not in sys.path:
        sys.path.append(str(relpath))
    for spec in specs:
        if ':' not in spec:
            raise Exception(f"Invalid entrypoint spec: {spec!r}, 必须形如 'module.path:attribute'")
        module_path, attr_name = spec.split(':', 1)
        try:
            module: types.ModuleType = importlib.import_module(module_path)
        except ImportError as e:
            raise Exception(f"无法导入模块 '{module_path}': {e}")
        if attr_name == '*':
            for k, v in module.__dict__.items():
                if not isinstance(v, Blueprint):
                    continue
                entrypoints.append(v)
        else:
            if not hasattr(module, attr_name):
                raise Exception(f"模块 '{module_path}' 中不存在属性 '{attr_name}'")
            entrypoints.append(getattr(module, attr_name))

    return entrypoints
