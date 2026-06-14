from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from api_blueprint.config import ResolvedApiTargetConfig
from api_blueprint.contract import ContractGraph


@dataclass(frozen=True)
class IrPluginContext:
    contract_graph: ContractGraph
    target: ResolvedApiTargetConfig
    project_root: Path
    out_dir: Path
    selected_routes: Sequence[Mapping[str, Any]]
    options: Mapping[str, Any]

    def write_text(self, relative_path: str | Path, content: str, *, overwrite: bool = True) -> Path:
        path = self._target_path(relative_path)
        if path.exists() and not overwrite:
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_json(self, relative_path: str | Path, payload: object, *, overwrite: bool = True) -> Path:
        return self.write_text(
            relative_path,
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            overwrite=overwrite,
        )

    def _target_path(self, relative_path: str | Path) -> Path:
        path = Path(relative_path)
        if path.is_absolute():
            raise ValueError("ir-plugin output path must be relative")
        return self.out_dir / path
