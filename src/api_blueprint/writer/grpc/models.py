from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


GrpcPreset = Literal["go", "python"]
GrpcLayout = Literal["source_relative", "go_package"]
GrpcSelectionKind = Literal["target", "job"]


@dataclass(frozen=True)
class GrpcGenerationJob:
    name: str
    lang: GrpcPreset
    out_dir: Path
    source_root: Path
    import_roots: tuple[Path, ...]
    proto_patterns: tuple[str, ...]
    proto_files: tuple[Path, ...]
    selection_kind: GrpcSelectionKind
    layout: GrpcLayout
    plugin_out: Path | None = None
    module: str | None = None
    module_root: Path | None = None
    expected_go_package_prefix: str | None = None

    @property
    def preset(self) -> GrpcPreset:
        return self.lang

    @property
    def output(self) -> Path:
        return self.out_dir

    @property
    def proto_root(self) -> Path:
        return self.source_root

    @property
    def include_paths(self) -> tuple[Path, ...]:
        return self.import_roots

    @property
    def effective_plugin_out(self) -> Path:
        return self.plugin_out or self.out_dir
