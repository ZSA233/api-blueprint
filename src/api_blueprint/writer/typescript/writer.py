from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Mapping, Sequence, Set, Union

from api_blueprint.route_selection import normalize_selection_rules
from api_blueprint.writer.core.base import BaseWriter
from api_blueprint.writer.core.files import ensure_filepath_open

from .blueprint import TypeScriptBlueprint


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("TypeScriptWriter")
logger.setLevel(logging.INFO)


class TypeScriptWriter(BaseWriter[TypeScriptBlueprint]):
    SHARED_DIR_NAME = "(shared)"

    def __init__(
        self,
        working_dir: Union[str, Path] = ".",
        *,
        base_url: str | None = None,
        base_url_expr: str | None = None,
        template_lang: str = "typescript",
        transport_kind: str = "http",
        transport_class_name: str = "DefaultTransport",
        allow_raw_ws: bool = True,
        overlay_name: str | None = None,
        frontend_mode: str = "external",
        include: Sequence[str] = (),
        exclude: Sequence[str] = (),
        wails_binding_manifest: Mapping[str, str] | None = None,
    ):
        super().__init__(working_dir)
        self.base_url = base_url or ""
        self.base_url_expr = base_url_expr
        self.rendered_base_url = base_url_expr if base_url_expr is not None else json.dumps(self.base_url)
        self.template_lang = template_lang
        self.transport_kind = transport_kind
        self.transport_class_name = transport_class_name
        self.allow_raw_ws = allow_raw_ws
        self.overlay_name = overlay_name
        self.frontend_mode = frontend_mode
        self.include = normalize_selection_rules(include)
        self.exclude = normalize_selection_rules(exclude)
        self.wails_binding_manifest = dict(wails_binding_manifest or {})
        self._written_files: Set[str] = set()

    @property
    def shared_dir_name(self) -> str:
        return self.SHARED_DIR_NAME

    @property
    def overlay_dir_name(self) -> str:
        if self.overlay_name is None:
            raise RuntimeError("overlay_name is required for overlay directory derivation")
        return f"({self.overlay_name})"

    def gen(self) -> None:
        for bp in self.bps:
            bp.build()
            bp.gen()

    @contextmanager
    def write_file(self, filepath: Union[str, Path], overwrite: bool = False):
        filepath_str = str(filepath)
        wrote = False
        with ensure_filepath_open(filepath_str, "w", overwrite=overwrite) as handle:
            if handle:
                wrote = True
            yield handle
        if wrote:
            logger.info("[+] Written: %s", filepath_str)
        else:
            logger.info("[.] Skipped: %s", filepath_str)
