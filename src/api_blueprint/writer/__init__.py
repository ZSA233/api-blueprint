from api_blueprint.engine import Blueprint
from pathlib import Path
from api_blueprint.engine.utils import snake_to_pascal_case
from typing import Union, List, TypeVar, Generic, get_args, get_origin


BB = TypeVar('BB', bound='BaseBlueprint')
BW = TypeVar('BW', bound='BaseWriter')


class BaseBlueprint(Generic[BW]):
    writer: BW
    bp: Blueprint

    def __init__(self, writer: BW, bp: Blueprint):
        self.writer = writer
        self.bp = bp

    @property
    def root_name(self) -> str:
        return self.bp.root.strip('/')

    def iter_router(self):
        yield from self.bp.iter_router()

    def build(self):
        self.bp.build()


class BaseWriter(Generic[BB]):
    bps: List[BB]
    working_dir: Path

    def __init__(self, working_dir: Union[str, Path] = '.'):
        self.bps = []
        self.working_dir = Path(working_dir)

    def _resolve_generic_parameter(self):
        orig = getattr(self, "__orig_class__", None)
        if orig is None:
            orig_bases = getattr(self, '__orig_bases__', None)
            for base in orig_bases:
                if get_origin(base) is BaseWriter:
                    (bb_cls,) = get_args(base)
                    return bb_cls
        else:
            (t_cls,) = get_args(orig)
            return t_cls
        raise RuntimeError("无法找到泛型信息")

    def register(self, *bps: List[Blueprint]):
        t_cls = self._resolve_generic_parameter()
        for bp in bps:
            self.bps.append(t_cls(self, bp))
