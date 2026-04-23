from __future__ import annotations

import glob
import re
from pathlib import Path
from typing import Sequence

from api_blueprint.config import ResolvedGrpcJobConfig, ResolvedGrpcTargetConfig

from .models import GrpcGenerationJob


GO_PACKAGE_PATTERN = re.compile(r'^\s*option\s+go_package\s*=\s*"([^"]+)"\s*;', re.MULTILINE)


def expand_job(
    job: ResolvedGrpcJobConfig,
    *,
    global_include_paths: Sequence[Path] = (),
) -> GrpcGenerationJob:
    source_root = job.proto_root.resolve()
    import_roots = merge_path_groups(global_include_paths, job.include_paths)
    proto_files = expand_patterns(source_root, job.name, job.protos, label="legacy/raw job")
    return GrpcGenerationJob(
        name=job.name,
        lang=job.preset,
        out_dir=job.output.resolve(),
        source_root=source_root,
        import_roots=import_roots,
        proto_patterns=job.protos,
        proto_files=proto_files,
        selection_kind="job",
        layout=job.layout,
        plugin_out=job.output.resolve(),
        module=job.module,
    )


def expand_target(
    target: ResolvedGrpcTargetConfig,
    *,
    global_import_roots: Sequence[Path] = (),
) -> GrpcGenerationJob:
    source_root = target.source_root.resolve()
    out_dir = target.out_dir.resolve()
    import_roots = merge_path_groups(global_import_roots, target.import_roots)
    proto_files = expand_patterns(source_root, target.id, target.files, label="target")

    if target.lang == "python":
        return GrpcGenerationJob(
            name=target.id,
            lang=target.lang,
            out_dir=out_dir,
            source_root=source_root,
            import_roots=import_roots,
            proto_patterns=target.files,
            proto_files=proto_files,
            selection_kind="target",
            layout="source_relative",
            plugin_out=out_dir,
            python_package_root=target.python_package_root,
            python_package_root_path=target.python_package_root_path,
        )

    module_root, module_path = discover_go_module(out_dir, target_id=target.id)
    expected_prefix = expected_go_package_prefix(out_dir=out_dir, module_root=module_root, module_path=module_path)
    validate_target_go_packages(
        target_id=target.id,
        source_root=source_root,
        out_dir=out_dir,
        proto_files=proto_files,
        module_root=module_root,
        module_path=module_path,
        expected_prefix=expected_prefix,
    )
    return GrpcGenerationJob(
        name=target.id,
        lang=target.lang,
        out_dir=out_dir,
        source_root=source_root,
        import_roots=import_roots,
        proto_patterns=target.files,
        proto_files=proto_files,
        selection_kind="target",
        layout="go_package",
        plugin_out=module_root,
        module=module_path,
        module_root=module_root,
        expected_go_package_prefix=expected_prefix,
    )


def merge_path_groups(*groups: Sequence[Path]) -> tuple[Path, ...]:
    merged: list[Path] = []
    seen: set[str] = set()
    for group in groups:
        for path in group:
            resolved = path.resolve()
            key = str(resolved)
            if key in seen:
                continue
            seen.add(key)
            merged.append(resolved)
    return tuple(merged)


def expand_patterns(source_root: Path, name: str, patterns: Sequence[str], *, label: str) -> tuple[Path, ...]:
    expanded: list[Path] = []
    seen: set[str] = set()
    for pattern in patterns:
        matches = expand_single_pattern(source_root, pattern)
        if not matches:
            raise ValueError(f"[gen_grpc] {label}[{name}] files 未匹配到 proto: {pattern}")
        for match in matches:
            key = match.as_posix()
            if key in seen:
                continue
            seen.add(key)
            expanded.append(match)
    return tuple(expanded)


def expand_single_pattern(source_root: Path, pattern: str) -> tuple[Path, ...]:
    if glob.has_magic(pattern):
        matches = sorted(path for path in source_root.glob(pattern) if path.is_file())
    else:
        candidate = (source_root / pattern).resolve()
        if not candidate.is_file():
            return ()
        matches = [candidate]

    return tuple(relative_to_root(source_root, match) for match in matches)


def relative_to_root(source_root: Path, path: Path) -> Path:
    resolved_root = source_root.resolve()
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(resolved_root)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"[gen_grpc] proto 文件超出 source_root 范围: {resolved_path}") from exc


def discover_go_module(out_dir: Path, *, target_id: str) -> tuple[Path, str]:
    for candidate in (out_dir.resolve(), *out_dir.resolve().parents):
        go_mod = candidate / "go.mod"
        if not go_mod.is_file():
            continue
        module_path = parse_go_module_path(go_mod)
        if module_path:
            return candidate, module_path
        raise ValueError(f"[gen_grpc] target[{target_id}] 无法从 {go_mod} 解析 Go module 路径")

    raise ValueError(
        f"[gen_grpc] target[{target_id}] 的 out_dir[{out_dir}] 不在任何包含 go.mod 的目录树中，"
        "Go target 需要据此自动推导模块路径。"
    )


def parse_go_module_path(go_mod_path: Path) -> str | None:
    for raw_line in go_mod_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue
        if not line.startswith("module "):
            continue
        parts = line.split()
        if len(parts) >= 2:
            return parts[1]
    return None


def expected_go_package_prefix(*, out_dir: Path, module_root: Path, module_path: str) -> str:
    relative_out = out_dir.resolve().relative_to(module_root.resolve())
    if relative_out == Path("."):
        return module_path
    return f"{module_path}/{relative_out.as_posix()}"


def validate_target_go_packages(
    *,
    target_id: str,
    source_root: Path,
    out_dir: Path,
    proto_files: Sequence[Path],
    module_root: Path,
    module_path: str,
    expected_prefix: str,
) -> None:
    for proto_file in proto_files:
        go_package = parse_proto_go_package(source_root / proto_file)
        if go_package is None:
            raise ValueError(
                f"[gen_grpc] target[{target_id}] proto[{proto_file.as_posix()}] 缺少 option go_package。\n"
                f"out_dir: {out_dir}\n"
                f"module_root: {module_root}\n"
                f"module_path: {module_path}\n"
                f"expected_go_package_prefix: {expected_prefix}"
            )

        import_path = go_package.split(";", 1)[0]
        if matches_go_package_prefix(import_path, expected_prefix):
            continue
        raise ValueError(
            f"[gen_grpc] target[{target_id}] proto[{proto_file.as_posix()}] 的 go_package 与 out_dir 不一致。\n"
            f"out_dir: {out_dir}\n"
            f"module_root: {module_root}\n"
            f"module_path: {module_path}\n"
            f"expected_go_package_prefix: {expected_prefix}\n"
            f"actual_go_package: {go_package}"
        )


def parse_proto_go_package(proto_path: Path) -> str | None:
    match = GO_PACKAGE_PATTERN.search(proto_path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def matches_go_package_prefix(import_path: str, expected_prefix: str) -> bool:
    return import_path == expected_prefix or import_path.startswith(expected_prefix + "/")
