from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


GrpcPreset = Literal["go", "python"]
GrpcLayout = Literal["source_relative", "go_package"]


@dataclass(frozen=True)
class GrpcGenerationJob:
    name: str
    preset: GrpcPreset
    output: Path
    proto_root: Path
    include_paths: tuple[Path, ...]
    proto_patterns: tuple[str, ...]
    proto_files: tuple[Path, ...]
    layout: GrpcLayout
    module: str | None = None
