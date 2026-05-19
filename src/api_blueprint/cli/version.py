from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import click

from api_blueprint._version import __version__

F = TypeVar("F", bound=Callable[..., object])


def api_blueprint_version_option(command_name: str) -> Callable[[F], F]:
    return click.version_option(
        version=__version__,
        prog_name=command_name,
        message=f"{command_name}, api-blueprint %(version)s",
        help=f"Show api-blueprint {__version__} and exit.",
    )
