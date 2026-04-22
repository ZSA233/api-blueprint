from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Union


class GolangToolchain:
    GO_ENUM_ARGS: Tuple[str, ...] = (
        "--names",
        "--values",
        "--marshal",
        "--mustparse",
        "--nocase",
        "--output-suffix",
        "_gen",
    )

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    @staticmethod
    def read_gomodule(path: str | Path) -> list[tuple[str, str]]:
        process = subprocess.run(
            ["go", "list", "-m", "-f", "{{.Path}} {{.Dir}}"],
            cwd=path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
        return [tuple(line.split(" ", 1)) for line in process.stdout.strip().splitlines()]

    def run_format(self, filepath: str | Path):
        file_or_dir = str(Path(filepath).absolute())
        try:
            process = subprocess.run(
                ["gofmt", "-s", "-w", file_or_dir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            self.logger.error("[x] gofmt: %s", exc.stderr.strip())
            return exc.stderr
        return process.stdout.strip()

    def run_go_enum(self, filepath: Union[str, Path], extra_args: Optional[list[str]] = None) -> None:
        executable = shutil.which("go-enum")
        if executable is None:
            self.logger.warning("[!] go-enum command not found, skip enum generation for %s", filepath)
            return

        file_path = Path(filepath).absolute()
        if not file_path.exists():
            self.logger.error("[x] go-enum target missing: %s", file_path)
            return

        args = list(extra_args or self.GO_ENUM_ARGS)
        command = [executable, *args, f"--file={file_path.name}"]
        try:
            subprocess.run(
                command,
                cwd=file_path.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            output = exc.stderr.strip() or exc.stdout.strip()
            self.logger.error("[x] go-enum failed for %s: %s", file_path, output)
