from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, IO, Optional


def ensure_filepath(filepath: str | Path) -> Path:
    path = Path(filepath).absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def ensure_filepath_open(
    file: str | Path,
    mode: str,
    buffering: int = -1,
    encoding: Optional[str] = None,
    errors: Optional[str] = None,
    newline: Optional[str] = None,
    closefd: bool = True,
    opener: Optional[Any] = None,
    overwrite: bool = True,
) -> Generator[Optional[IO], None, None]:
    path = ensure_filepath(file)
    if not overwrite and path.exists():
        yield None
        return

    if encoding is None and "b" not in mode:
        encoding = "utf-8"

    with open(path, mode, buffering, encoding, errors, newline, closefd, opener) as handle:
        yield handle


class SafeFmtter(str):
    def format(self, *args: Any, **kwargs: Any) -> str:
        try:
            return str.format(self, *args, **kwargs)
        except KeyError:
            return str(self)
