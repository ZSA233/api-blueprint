from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AbcQuery:
    arg1: bool | None = None
    arg3: str | None = None
    arg2: float | None = None


@dataclass
class HelloWayQuery:
    arg1: Any | None = None
