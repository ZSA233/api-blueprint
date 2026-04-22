from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Optional, Set, Union

from api_blueprint.writer.core.base import BaseWriter
from api_blueprint.writer.core.files import ensure_filepath_open

from .blueprint import TypeScriptBlueprint


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("TypeScriptWriter")
logger.setLevel(logging.INFO)


class TypeScriptWriter(BaseWriter[TypeScriptBlueprint]):
    def __init__(self, working_dir: Union[str, Path] = ".", *, base_url: str | None = None):
        super().__init__(working_dir)
        self.base_url = base_url or ""
        self._written_files: Set[str] = set()

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
