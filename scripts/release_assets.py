#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import zipfile
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from api_blueprint.release_version import ReleaseVersionError, parse_release_tag
from scripts.release_version import check_sync

README_PATH = Path("README.md")
README_EN_PATH = Path("README_EN.md")
PRE_README_PATH = Path("PRE_README.MD")
AGENTS_PATH = Path("AGENTS.MD")
RELEASE_DOC_PATH = Path("docs/release-process.md")


class ReleaseAssetsError(RuntimeError):
    pass


@dataclass(frozen=True)
class DistArtifacts:
    wheels: list[Path]
    sdists: list[Path]


def _venv_python_path(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def _run_git(repo_root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"git {' '.join(args)} failed"
        raise ReleaseAssetsError(message)
    return result.stdout.strip()


def _branch_ref(branch: str) -> str:
    return f"refs/heads/{branch}"


def _resolve_remote_branch_sha(repo_root: Path, *, remote: str, branch: str) -> str | None:
    branch_ref = _branch_ref(branch)
    output = _run_git(repo_root, ["ls-remote", "--heads", "--refs", remote, branch_ref])
    if not output:
        return None

    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ReleaseAssetsError(
            f"expected at most one remote ref for {remote}/{branch}, found {len(lines)}"
        )

    parts = lines[0].split()
    if len(parts) != 2:
        raise ReleaseAssetsError(f"unexpected ls-remote output for {remote}/{branch}: {lines[0]!r}")

    sha, ref = parts
    if ref != branch_ref:
        raise ReleaseAssetsError(
            f"unexpected remote ref for {remote}/{branch}: expected {branch_ref}, found {ref}"
        )
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ReleaseAssetsError(f"unexpected remote SHA for {remote}/{branch}: {sha}")
    return sha


def _push_branch_ref(
    repo_root: Path,
    *,
    remote: str,
    branch: str,
    target_commit: str,
    expected_remote_sha: str | None,
) -> None:
    destination = f"{target_commit}:{_branch_ref(branch)}"
    if expected_remote_sha is None:
        _run_git(repo_root, ["push", remote, destination])
        return

    lease = f"--force-with-lease={_branch_ref(branch)}:{expected_remote_sha}"
    _run_git(repo_root, ["push", lease, remote, destination])


def _uv_path() -> str:
    uv = shutil.which("uv")
    if uv is None:
        raise ReleaseAssetsError("uv executable not found in PATH")
    return uv


def validate_config(repo_root: Path) -> None:
    required_paths = [
        README_PATH,
        README_EN_PATH,
        PRE_README_PATH,
        AGENTS_PATH,
        RELEASE_DOC_PATH,
        Path("release-version.toml"),
        Path("Makefile"),
        Path(".github/workflows/ci.yml"),
        Path(".github/workflows/release-rc.yml"),
        Path(".github/workflows/release.yml"),
        Path(".github/actions/release-bundle/action.yml"),
        Path("scripts/release_version.py"),
        Path("scripts/release_assets.py"),
    ]
    missing = [str(path) for path in required_paths if not (repo_root / path).exists()]
    if missing:
        raise ReleaseAssetsError("missing required release-contract files:\n" + "\n".join(missing))
    check_sync(repo_root)


def _markdown_structure(path: Path) -> tuple[list[int], int, int]:
    heading_levels: list[int] = []
    code_block_count = 0
    table_count = 0
    in_code_block = False
    separator_re = re.compile(r"^\|(?:\s*:?-+:?\s*\|)+$")
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        if line.startswith("```"):
            in_code_block = not in_code_block
            if in_code_block:
                code_block_count += 1
            continue
        if in_code_block:
            continue
        if match := re.match(r"^(#{1,6})\s+", line):
            heading_levels.append(len(match.group(1)))
        if separator_re.fullmatch(line.strip()):
            table_count += 1
    return heading_levels, code_block_count, table_count


def validate_docs(repo_root: Path) -> None:
    readme = repo_root / README_PATH
    readme_en = repo_root / README_EN_PATH
    zh_structure = _markdown_structure(readme)
    en_structure = _markdown_structure(readme_en)
    if zh_structure != en_structure:
        raise ReleaseAssetsError(
            "README mirror structure mismatch between README.md and README_EN.md"
        )


def validate_release_version(repo_root: Path, tag: str) -> None:
    check_sync(repo_root, expected_tag=tag)


def collect_dist_artifacts(dist_dir: Path) -> DistArtifacts:
    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    return DistArtifacts(wheels=wheels, sdists=sdists)


def _assert_wheel_contains(wheel_path: Path, prefix: str) -> None:
    with zipfile.ZipFile(wheel_path) as zf:
        if not any(name.startswith(prefix) for name in zf.namelist()):
            raise ReleaseAssetsError(f"{wheel_path.name} is missing packaged files under {prefix}")


def validate_dist_artifacts(dist_dir: Path) -> DistArtifacts:
    artifacts = collect_dist_artifacts(dist_dir)
    if len(artifacts.wheels) != 1:
        raise ReleaseAssetsError(f"expected exactly one wheel in {dist_dir}, found {len(artifacts.wheels)}")
    if len(artifacts.sdists) != 1:
        raise ReleaseAssetsError(
            f"expected exactly one source distribution in {dist_dir}, found {len(artifacts.sdists)}"
        )

    wheel_path = artifacts.wheels[0]
    _assert_wheel_contains(wheel_path, "api_blueprint/writer/templates/")
    _assert_wheel_contains(wheel_path, "api_blueprint/hub/templates/")
    _assert_wheel_contains(wheel_path, "api_blueprint/static/")
    return artifacts


def install_check(repo_root: Path, dist_dir: Path, tag: str) -> None:
    validate_release_version(repo_root, tag)
    artifacts = validate_dist_artifacts(dist_dir)
    wheel_path = artifacts.wheels[0]
    uv = _uv_path()

    with tempfile.TemporaryDirectory(prefix="api-blueprint-install-check-") as tmp_dir:
        venv_dir = Path(tmp_dir) / "venv"
        _run([uv, "venv", str(venv_dir)], cwd=repo_root)
        python_bin = _venv_python_path(venv_dir)

        _run([uv, "pip", "install", "--python", str(python_bin), str(wheel_path)], cwd=repo_root)

        smoke = textwrap.dedent(
            """
            import importlib.metadata as metadata
            import importlib.resources as resources
            from click.testing import CliRunner
            import api_blueprint
            from api_blueprint.cli.apidoc import apidoc_server
            from api_blueprint.cli.apigen import gen_golang, gen_typescript

            assert api_blueprint.__version__
            expected_entrypoints = {
                "api-doc-server": "api_blueprint.cli.apidoc:apidoc_server",
                "api-gen-golang": "api_blueprint.cli.apigen:gen_golang",
                "api-gen-typescript": "api_blueprint.cli.apigen:gen_typescript",
            }
            entrypoints = {ep.name: ep.value for ep in metadata.entry_points(group="console_scripts")}
            for name, value in expected_entrypoints.items():
                assert entrypoints.get(name) == value, (name, entrypoints.get(name))

            runner = CliRunner()
            for cli in (apidoc_server, gen_golang, gen_typescript):
                result = runner.invoke(cli, ["--help"])
                assert result.exit_code == 0, result.output

            static_dir = resources.files("api_blueprint") / "static"
            hub_templates_dir = resources.files("api_blueprint") / "hub" / "templates"
            writer_templates_dir = resources.files("api_blueprint") / "writer" / "templates"

            assert static_dir.joinpath("swagger-ui.css").is_file()
            assert hub_templates_dir.joinpath("index.html").is_file()
            assert writer_templates_dir.joinpath("typescript").is_dir()
            """
        ).strip()
        _run([str(python_bin), "-c", smoke], cwd=repo_root)


def sync_stable_ref(repo_root: Path, tag: str, branch: str = "stable") -> None:
    release = parse_release_tag(tag)
    if release.is_rc:
        raise ReleaseAssetsError("stable branch can only be synced from a stable tag")

    target_commit = _run_git(repo_root, ["rev-list", "-n", "1", tag])
    if not target_commit:
        raise ReleaseAssetsError(f"could not resolve commit for tag {tag}")

    remote_sha = _resolve_remote_branch_sha(repo_root, remote="origin", branch=branch)
    _push_branch_ref(
        repo_root,
        remote="origin",
        branch=branch,
        target_commit=target_commit,
        expected_remote_sha=remote_sha,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate api-blueprint release assets.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate-config", help="Validate required release-contract files exist")
    subparsers.add_parser("validate-docs", help="Validate README mirror structure")

    validate_version_parser = subparsers.add_parser(
        "validate-release-version", help="Validate current repository state matches a release tag"
    )
    validate_version_parser.add_argument("--tag", required=True, help="Expected release tag")

    install_parser = subparsers.add_parser(
        "install-check", help="Validate built artifacts and smoke-test an installed wheel"
    )
    install_parser.add_argument("--tag", required=True, help="Expected release tag")
    install_parser.add_argument(
        "--dist-dir",
        default="dist",
        type=Path,
        help="Directory containing built release artifacts",
    )

    sync_parser = subparsers.add_parser(
        "sync-stable-ref", help="Move the remote stable branch to the specified stable tag"
    )
    sync_parser.add_argument("--tag", required=True, help="Stable tag to sync from")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "validate-config":
            validate_config(PROJECT_ROOT)
            return 0
        if args.command == "validate-docs":
            validate_docs(PROJECT_ROOT)
            return 0
        if args.command == "validate-release-version":
            validate_release_version(PROJECT_ROOT, args.tag)
            return 0
        if args.command == "install-check":
            install_check(PROJECT_ROOT, args.dist_dir, args.tag)
            return 0
        if args.command == "sync-stable-ref":
            sync_stable_ref(PROJECT_ROOT, args.tag)
            return 0
    except (ReleaseAssetsError, ReleaseVersionError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
