#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from api_blueprint.release_version import (
    ReleaseVersion,
    ReleaseVersionConfig,
    ReleaseVersionError,
    load_release_version_config,
    parse_base_version,
    parse_release_tag,
    read_python_version_file,
    render_python_version_file,
    render_release_version_config,
)

RELEASE_VERSION_PATH = Path("release-version.toml")
VERSION_FILE_PATH = Path("src/api_blueprint/_version.py")
MANAGED_VERSION_PATHS = (
    RELEASE_VERSION_PATH,
    VERSION_FILE_PATH,
)


class ReleaseVersionToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class RepositoryVersionState:
    config: ReleaseVersionConfig
    python_version: str


def _read_text(repo_root: Path, relative_path: Path) -> str:
    return (repo_root / relative_path).read_text(encoding="utf-8")


def _write_text(repo_root: Path, relative_path: Path, content: str) -> None:
    path = repo_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def capture_managed_version_files(repo_root: Path) -> dict[Path, str | None]:
    snapshots: dict[Path, str | None] = {}
    for relative_path in MANAGED_VERSION_PATHS:
        path = repo_root / relative_path
        snapshots[relative_path] = path.read_text(encoding="utf-8") if path.exists() else None
    return snapshots


def restore_managed_version_files(repo_root: Path, snapshots: dict[Path, str | None]) -> None:
    for relative_path, content in snapshots.items():
        path = repo_root / relative_path
        if content is None:
            path.unlink(missing_ok=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def collect_repository_version_state(repo_root: Path) -> RepositoryVersionState:
    config = load_release_version_config(repo_root / RELEASE_VERSION_PATH)
    python_version = read_python_version_file(repo_root / VERSION_FILE_PATH)
    return RepositoryVersionState(config=config, python_version=python_version)


def check_sync(repo_root: Path, expected_tag: str | None = None) -> ReleaseVersion:
    state = collect_repository_version_state(repo_root)
    expected_release = state.config.release
    problems: list[str] = []

    if state.python_version != expected_release.python_version:
        problems.append(
            f"{VERSION_FILE_PATH} has {state.python_version}, expected {expected_release.python_version}"
        )

    if expected_tag is not None:
        parsed_tag = parse_release_tag(expected_tag)
        if parsed_tag != expected_release:
            problems.append(
                f"release tag {expected_tag} does not match release-version.toml ({expected_release.tag})"
            )

    if problems:
        raise ReleaseVersionToolError("\n".join(problems))

    return expected_release


def write_release_version_config(repo_root: Path, config: ReleaseVersionConfig) -> None:
    _write_text(repo_root, RELEASE_VERSION_PATH, render_release_version_config(config))


def write_python_version(repo_root: Path, version: str) -> None:
    _write_text(repo_root, VERSION_FILE_PATH, render_python_version_file(version))


def set_release_version(
    repo_root: Path,
    config: ReleaseVersionConfig,
    *,
    check: bool = False,
) -> ReleaseVersion:
    snapshots = capture_managed_version_files(repo_root)
    try:
        write_release_version_config(repo_root, config)
        write_python_version(repo_root, config.release.python_version)
        if check:
            check_sync(repo_root, expected_tag=config.release.tag)
    except Exception:
        restore_managed_version_files(repo_root, snapshots)
        raise
    return config.release


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage api-blueprint release version files.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("show", help="Show current derived release metadata")

    check_parser = subparsers.add_parser("check-sync", help="Validate version files are in sync")
    check_parser.add_argument("--tag", dest="tag", help="Expected git tag")

    rc_parser = subparsers.add_parser("set-rc", help="Switch repository version metadata to RC")
    rc_parser.add_argument("--base", required=True, help="Base version in X.Y.Z format")
    rc_parser.add_argument("--rc", required=True, type=int, help="RC number")
    rc_parser.add_argument("--check", action="store_true", help="Run sync validation after update")

    stable_parser = subparsers.add_parser(
        "set-stable", help="Switch repository version metadata to stable"
    )
    stable_parser.add_argument("--base", required=True, help="Base version in X.Y.Z format")
    stable_parser.add_argument("--check", action="store_true", help="Run sync validation after update")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "show":
            release = check_sync(PROJECT_ROOT)
            print(f"base_version={release.base_version}")
            print(f"python_version={release.python_version}")
            print(f"tag={release.tag}")
            print(f"channel={'rc' if release.is_rc else 'stable'}")
            return 0

        if args.command == "check-sync":
            release = check_sync(PROJECT_ROOT, expected_tag=args.tag)
            print(release.tag)
            return 0

        if args.command == "set-rc":
            base_version = parse_base_version(args.base)
            if args.rc <= 0:
                raise ReleaseVersionToolError("--rc must be a positive integer")
            config = ReleaseVersionConfig(base_version=base_version, channel="rc", rc_number=args.rc)
            release = set_release_version(PROJECT_ROOT, config, check=args.check)
            print(release.tag)
            return 0

        if args.command == "set-stable":
            base_version = parse_base_version(args.base)
            config = ReleaseVersionConfig(base_version=base_version, channel="stable")
            release = set_release_version(PROJECT_ROOT, config, check=args.check)
            print(release.tag)
            return 0
    except (ReleaseVersionError, ReleaseVersionToolError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
