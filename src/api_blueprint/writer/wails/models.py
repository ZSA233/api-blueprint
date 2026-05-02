from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


WailsVersion = Literal["v2", "v3"]


@dataclass(frozen=True)
class WailsGenerationTarget:
    id: str
    version: WailsVersion
    go_out_dir: Path
    typescript_out_dir: Path
