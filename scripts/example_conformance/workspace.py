from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scripts import example_validation


@dataclass(frozen=True)
class ConformanceWorkspace:
    blueprint: example_validation.BlueprintExampleWorkspace
    temporary: bool

    @property
    def root(self) -> Path:
        return self.blueprint.root


def prepare_generated_workspace(repo_root: Path) -> ConformanceWorkspace:
    workspace = example_validation.prepare_blueprint_workspace(repo_root)
    example_validation.regenerate_blueprint_examples(workspace)
    return ConformanceWorkspace(workspace, temporary=True)


def repo_workspace(repo_root: Path) -> ConformanceWorkspace:
    return ConformanceWorkspace(example_validation._blueprint_workspace(repo_root / "examples"), temporary=False)


def refresh_repo_workspace(repo_root: Path) -> ConformanceWorkspace:
    example_validation.regenerate_repo_blueprint_examples(repo_root)
    return repo_workspace(repo_root)


def validate_snapshot(repo_root: Path, workspace: ConformanceWorkspace) -> None:
    example_validation.validate_example_snapshots(repo_root, workspace.blueprint)


def compile_workspace(workspace: ConformanceWorkspace) -> None:
    example_validation.compile_generated_examples(workspace.blueprint)

