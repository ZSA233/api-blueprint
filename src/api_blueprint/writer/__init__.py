from api_blueprint.writer.core import (
    BaseBlueprint,
    BaseWriter,
    GeneratorTargetSpec,
    SafeFmtter,
    ensure_default_targets,
    ensure_filepath,
    ensure_filepath_open,
    get_target,
    iter_targets,
    load_templates,
    register_target,
)

ensure_default_targets()

from api_blueprint.writer import golang, typescript  # noqa: E402,F401

__all__ = (
    "BaseBlueprint",
    "BaseWriter",
    "GeneratorTargetSpec",
    "SafeFmtter",
    "ensure_default_targets",
    "ensure_filepath",
    "ensure_filepath_open",
    "get_target",
    "iter_targets",
    "load_templates",
    "register_target",
)
