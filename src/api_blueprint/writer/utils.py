
from datetime import datetime
from typing import Optional, Any, Generator, IO
from contextlib import contextmanager
from pathlib import Path
import logging


def ensure_filepath(filepath: str):
    fp = Path(filepath).absolute()
    fp.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def ensure_filepath_open(
    file: str,
    mode: str,
    buffering: int = -1,
    encoding: Optional[str] = None,
    errors: Optional[str] = None,
    newline: Optional[str] = None,
    closefd: bool = True,
    opener: Optional[Any] = None,
    overwrite: bool = True,
) -> Generator[Optional[IO], None, None]:
    ensure_filepath(file)
    if not overwrite and Path(file).exists():
        yield None
        return
    
    with open(file, mode, buffering, encoding, errors, newline, closefd, opener) as f:
        yield f



class SafeFmtter(str):
    def format(self, *args, **kwargs) -> str:
        try:
            return str.format(self, *args, **kwargs)
        except KeyError:
            return str(self)
            