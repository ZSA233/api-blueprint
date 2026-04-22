from __future__ import annotations

from pathlib import Path
from typing import Generic, TypeVar, Union, get_args, get_origin

from api_blueprint.engine import Blueprint

BB = TypeVar("BB", bound="BaseBlueprint")
BW = TypeVar("BW", bound="BaseWriter")


class BaseBlueprint(Generic[BW]):
    writer: BW
    bp: Blueprint

    def __init__(self, writer: BW, bp: Blueprint):
        self.writer = writer
        self.bp = bp

    @property
    def root_name(self) -> str:
        return self.bp.root.strip("/")

    def iter_router(self):
        yield from self.bp.iter_router()

    def build(self) -> None:
        self.bp.build()


class BaseWriter(Generic[BB]):
    bps: list[BB]
    working_dir: Path

    def __init__(self, working_dir: Union[str, Path] = "."):
        self.bps = []
        self.working_dir = Path(working_dir)

    def _resolve_generic_parameter(self):
        orig = getattr(self, "__orig_class__", None)
        if orig is None:
            for base in getattr(self, "__orig_bases__", ()) or ():
                if get_origin(base) is BaseWriter:
                    (bb_cls,) = get_args(base)
                    return bb_cls
        else:
            (bb_cls,) = get_args(orig)
            return bb_cls
        raise RuntimeError("无法找到泛型信息")

    def register(self, *bps: Blueprint):
        blueprint_type = self._resolve_generic_parameter()
        for blueprint in bps:
            self.bps.append(blueprint_type(self, blueprint))
