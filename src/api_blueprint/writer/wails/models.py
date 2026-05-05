from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


WailsVersion = Literal["v2", "v3"]
WailsFrontendMode = Literal["external", "none"]


@dataclass(frozen=True)
class WailsGenerationTarget:
    id: str
    version: WailsVersion
    overlay_name: str
    frontend_mode: WailsFrontendMode
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    go_transport_dir: Path
    go_service_pattern: str
    go_route_overlay_pattern: str
    typescript_route_overlay_pattern: str | None
    typescript_transport_pattern: str | None
