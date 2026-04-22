from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BASE_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
PYTHON_VERSION_RE = re.compile(r"^(?P<base>\d+\.\d+\.\d+)(?:rc(?P<rc>[1-9]\d*))?$")
RELEASE_TAG_RE = re.compile(r"^v(?P<base>\d+\.\d+\.\d+)(?:-rc\.(?P<rc>[1-9]\d*))?$")
VERSION_ASSIGNMENT_RE = re.compile(r'^(__version__\s*=\s*")([^"]+)("\s*)$', re.MULTILINE)


class ReleaseVersionError(ValueError):
    pass


@dataclass(frozen=True)
class ReleaseVersion:
    base_version: str
    rc_number: int | None = None

    @property
    def is_rc(self) -> bool:
        return self.rc_number is not None

    @property
    def python_version(self) -> str:
        if self.rc_number is None:
            return self.base_version
        return f"{self.base_version}rc{self.rc_number}"

    @property
    def tag(self) -> str:
        if self.rc_number is None:
            return f"v{self.base_version}"
        return f"v{self.base_version}-rc.{self.rc_number}"


@dataclass(frozen=True)
class ReleaseVersionConfig:
    base_version: str
    channel: str
    rc_number: int | None = None

    @property
    def release(self) -> ReleaseVersion:
        if self.channel == "stable":
            return ReleaseVersion(base_version=self.base_version)
        return ReleaseVersion(base_version=self.base_version, rc_number=self.rc_number)


def parse_base_version(value: str) -> str:
    if not BASE_VERSION_RE.fullmatch(value):
        raise ReleaseVersionError(f"invalid base version: {value!r}")
    return value


def parse_python_release_version(value: str) -> ReleaseVersion:
    match = PYTHON_VERSION_RE.fullmatch(value)
    if not match:
        raise ReleaseVersionError(f"invalid python release version: {value!r}")
    base_version = parse_base_version(match.group("base"))
    rc_number = match.group("rc")
    return ReleaseVersion(
        base_version=base_version,
        rc_number=int(rc_number) if rc_number is not None else None,
    )


def parse_release_tag(value: str) -> ReleaseVersion:
    match = RELEASE_TAG_RE.fullmatch(value)
    if not match:
        raise ReleaseVersionError(f"invalid release tag: {value!r}")
    base_version = parse_base_version(match.group("base"))
    rc_number = match.group("rc")
    return ReleaseVersion(
        base_version=base_version,
        rc_number=int(rc_number) if rc_number is not None else None,
    )


def parse_release_version_config(payload: dict[str, Any]) -> ReleaseVersionConfig:
    allowed_keys = {"base_version", "channel", "rc_number"}
    unexpected = sorted(set(payload) - allowed_keys)
    if unexpected:
        raise ReleaseVersionError(
            "release-version.toml contains unsupported keys: " + ", ".join(unexpected)
        )

    base_version = payload.get("base_version")
    channel = payload.get("channel")
    rc_number = payload.get("rc_number")

    if not isinstance(base_version, str):
        raise ReleaseVersionError("release-version.toml base_version must be a string")
    if not isinstance(channel, str):
        raise ReleaseVersionError("release-version.toml channel must be a string")

    parse_base_version(base_version)

    if channel not in {"stable", "rc"}:
        raise ReleaseVersionError("release-version.toml channel must be 'stable' or 'rc'")

    if channel == "stable":
        if "rc_number" in payload:
            raise ReleaseVersionError(
                "release-version.toml rc_number is only allowed when channel = 'rc'"
            )
        return ReleaseVersionConfig(base_version=base_version, channel=channel)

    if not isinstance(rc_number, int) or isinstance(rc_number, bool) or rc_number <= 0:
        raise ReleaseVersionError(
            "release-version.toml rc_number must be a positive integer when channel = 'rc'"
        )
    return ReleaseVersionConfig(base_version=base_version, channel=channel, rc_number=rc_number)


def render_release_version_config(config: ReleaseVersionConfig) -> str:
    lines = [
        "# Single source of truth for release-critical version metadata.",
        "# Python version: X.Y.Z / X.Y.ZrcN",
        "# Git tag: vX.Y.Z / vX.Y.Z-rc.N",
        "",
        f'base_version = "{config.base_version}"',
        f'channel = "{config.channel}"',
    ]
    if config.channel == "rc":
        lines.append(f"rc_number = {config.rc_number}")
    return "\n".join(lines) + "\n"


def load_release_version_config(path: Path) -> ReleaseVersionConfig:
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ReleaseVersionError(f"{path} is not valid TOML: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReleaseVersionError("release-version.toml must contain a TOML table")
    return parse_release_version_config(payload)


def read_python_version_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = VERSION_ASSIGNMENT_RE.search(text)
    if not match:
        raise ReleaseVersionError(f"could not locate __version__ assignment in {path}")
    return match.group(2)


def render_python_version_file(version: str) -> str:
    parse_python_release_version(version)
    return f'__version__ = "{version}"\n'

