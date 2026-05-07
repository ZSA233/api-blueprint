from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Sequence

from api_blueprint.config import ResolvedApiTargetConfig


SubprocessRunner = Callable[..., subprocess.CompletedProcess[Any]]
ProtocMain = Callable[[list[str]], int]


def select_proto_files(proto_root: Path, patterns: Sequence[str]) -> tuple[Path, ...]:
    matches: list[Path] = []
    seen: set[str] = set()
    for pattern in patterns:
        for path in proto_root.glob(pattern):
            if not path.is_file() or path.suffix != ".proto":
                continue
            relative = path.relative_to(proto_root)
            key = relative.as_posix()
            if key in seen:
                continue
            seen.add(key)
            matches.append(relative)
    if not matches:
        raise FileNotFoundError(f"no proto files matched under {proto_root}: {', '.join(patterns)}")
    return tuple(sorted(matches, key=lambda path: path.as_posix()))


def generate_go_stubs(
    proto_root: Path,
    target: ResolvedApiTargetConfig,
    *,
    runner: SubprocessRunner = subprocess.run,
) -> None:
    _require_target_out_dir(target)
    _require_executables("protoc", "protoc-gen-go", "protoc-gen-go-grpc")
    source_root = _source_root(proto_root, target)
    files = select_proto_files(source_root, target.files)
    target.out_dir.mkdir(parents=True, exist_ok=True)
    go_options, go_grpc_options = _go_output_options(target)
    command = [
        "protoc",
        *_include_args(source_root, (proto_root, *target.import_roots)),
        f"--go_out={target.out_dir.as_posix()}",
        *go_options,
        f"--go-grpc_out={target.out_dir.as_posix()}",
        *go_grpc_options,
        *[path.as_posix() for path in files],
    ]
    runner(command, cwd=source_root, check=True)


def generate_python_stubs(
    proto_root: Path,
    target: ResolvedApiTargetConfig,
    *,
    protoc_main: ProtocMain | None = None,
    builtin_proto_root: Path | None = None,
) -> None:
    _require_target_out_dir(target)
    source_root = _source_root(proto_root, target)
    files = select_proto_files(source_root, target.files)
    if protoc_main is None or builtin_proto_root is None:
        loaded_main, loaded_builtin_root = _load_grpc_tools()
        protoc_main = protoc_main or loaded_main
        builtin_proto_root = builtin_proto_root or loaded_builtin_root

    output_root = _python_output_root(target)
    output_root.mkdir(parents=True, exist_ok=True)
    args = [
        "grpc_tools.protoc",
        *_include_args(source_root, (proto_root, *target.import_roots, builtin_proto_root)),
        f"--python_out={output_root.as_posix()}",
        f"--grpc_python_out={output_root.as_posix()}",
        f"--pyi_out={output_root.as_posix()}",
        *[path.as_posix() for path in files],
    ]
    with _chdir(source_root):
        code = protoc_main(args)
    if code != 0:
        raise RuntimeError(f"grpc_tools.protoc exited with status {code}: target[{target.id}]")

    if target.python_package_root:
        _ensure_python_package_root(target.out_dir, _python_package_parts(target.python_package_root))
    _ensure_python_packages(output_root)
    if target.python_package_root:
        _rewrite_python_imports(output_root, _python_import_root(target.python_package_root))


def _require_target_out_dir(target: ResolvedApiTargetConfig) -> None:
    if target.out_dir is None:
        raise ValueError(f"target[{target.id}] {target.kind} requires out_dir")


def _go_output_options(target: ResolvedApiTargetConfig) -> tuple[list[str], list[str]]:
    if target.module:
        return (
            [f"--go_opt=module={target.module}"],
            [f"--go-grpc_opt=module={target.module}"],
        )
    return (
        ["--go_opt=paths=source_relative"],
        ["--go-grpc_opt=paths=source_relative"],
    )


def _source_root(proto_root: Path, target: ResolvedApiTargetConfig) -> Path:
    return target.source_root if target.source_root is not None else proto_root


def _require_executables(*names: str) -> None:
    missing = [name for name in names if shutil.which(name) is None]
    if missing:
        raise FileNotFoundError(f"[grpc][go] missing required executables: {', '.join(missing)}")


def _include_args(proto_root: Path, import_roots: Sequence[Path]) -> list[str]:
    roots: list[Path] = [proto_root, *import_roots]
    unique: list[str] = []
    seen: set[str] = set()
    for root in roots:
        key = root.as_posix()
        if key in seen:
            continue
        seen.add(key)
        unique.append(f"-I{key}")
    return unique


def _load_grpc_tools() -> tuple[ProtocMain, Path]:
    try:
        from grpc_tools import protoc
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "[grpc][python] Python gRPC generation requires grpcio-tools; install `grpcio-tools` and retry."
        ) from exc
    return protoc.main, Path(protoc.__file__).resolve().parent / "_proto"


def _python_output_root(target: ResolvedApiTargetConfig) -> Path:
    if target.out_dir is None:
        raise ValueError(f"target[{target.id}] {target.kind} requires out_dir")
    if not target.python_package_root:
        return target.out_dir
    return target.out_dir.joinpath(*_python_package_parts(target.python_package_root))


def _python_import_root(package_root: str) -> str:
    return ".".join(_python_package_parts(package_root))


def _python_package_parts(package_root: str) -> tuple[str, ...]:
    return tuple(part for part in re.split(r"[./]+", package_root) if part)


def _ensure_python_packages(output_root: Path) -> None:
    if output_root.exists():
        for directory, _dirs, files in os.walk(output_root):
            dir_path = Path(directory)
            if any(name.endswith((".py", ".pyi")) for name in files) or dir_path == output_root:
                (dir_path / "__init__.py").touch()


def _ensure_python_package_root(out_dir: Path | None, parts: Sequence[str]) -> None:
    if out_dir is None:
        return
    current = out_dir
    for part in parts:
        current = current / part
        current.mkdir(parents=True, exist_ok=True)
        (current / "__init__.py").touch()


def _rewrite_python_imports(output_root: Path, package_root: str) -> None:
    top_level_packages = sorted(path.name for path in output_root.iterdir() if path.is_dir())
    if not top_level_packages:
        return
    top_pattern = "|".join(re.escape(name) for name in top_level_packages)
    from_import = re.compile(rf"^from ({top_pattern})([.\w]*) import (.+_pb2(?:_grpc)?(?: as \w+)?)$", re.MULTILINE)
    direct_import = re.compile(rf"^import ((?:{top_pattern})(?:[.\w]*)?_pb2(?:_grpc)?)( as \w+)$", re.MULTILINE)

    for path in output_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        rewritten = from_import.sub(lambda match: f"from {package_root}.{match.group(1)}{match.group(2)} import {match.group(3)}", text)
        rewritten = direct_import.sub(lambda match: f"import {package_root}.{match.group(1)}{match.group(2)}", rewritten)
        if rewritten != text:
            path.write_text(rewritten, encoding="utf-8")


@contextmanager
def _chdir(path: Path) -> Generator[None, None, None]:
    current = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(current)
