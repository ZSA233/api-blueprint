from __future__ import annotations

import keyword
from pathlib import Path


def validate_python_package_root(value: str) -> str:
    if not value:
        raise ValueError("grpc python_package_root must not be empty")

    parts = value.split(".")
    if any(not part for part in parts):
        raise ValueError(
            "grpc python_package_root must be a dotted Python package path without leading, trailing, or repeated dots"
        )

    invalid = [part for part in parts if not part.isidentifier() or keyword.iskeyword(part)]
    if invalid:
        raise ValueError(
            "grpc python_package_root contains invalid Python package segments: " + ", ".join(invalid)
        )

    return value


def python_package_root_to_path(value: str) -> Path:
    return Path(*value.split("."))
