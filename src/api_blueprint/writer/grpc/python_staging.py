from __future__ import annotations

import re
import tempfile
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Sequence

from .models import GrpcGenerationJob


IMPORT_PATTERN = re.compile(
    r'^(?P<prefix>\s*import\s+(?:(?:public|weak)\s+)?)"(?P<path>[^"]+)"(?P<suffix>\s*;[^\r\n]*)$',
    re.MULTILINE,
)


@dataclass(frozen=True)
class PreparedPythonProtocRun:
    working_directory: Path
    include_args: tuple[str, ...]
    proto_args: tuple[str, ...]


@dataclass(frozen=True)
class StagedPythonProto:
    import_path: Path
    source_path: Path
    contents: str


@contextmanager
def prepare_python_protoc_run(job: GrpcGenerationJob) -> Generator[PreparedPythonProtocRun, None, None]:
    if job.python_package_root_path is None:
        yield PreparedPythonProtocRun(
            working_directory=job.source_root,
            include_args=(f"-I{job.source_root}", *(f"-I{path}" for path in job.import_roots)),
            proto_args=tuple(path.as_posix() for path in job.proto_files),
        )
        return

    virtual_root = job.python_package_root_path.as_posix()
    proto_roots = (job.source_root.resolve(), *(path.resolve() for path in job.import_roots))
    selected_import_paths = tuple(path.as_posix() for path in job.proto_files)

    with tempfile.TemporaryDirectory(prefix="api-blueprint-grpc-python-") as tmp_dir:
        shadow_root = Path(tmp_dir) / "shadow"
        shadow_root.mkdir(parents=True, exist_ok=True)

        staged = stage_python_protos(
            selected_import_paths=selected_import_paths,
            proto_roots=proto_roots,
            virtual_root=virtual_root,
        )
        for proto in staged.values():
            target_path = shadow_root / proto.import_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(proto.contents, encoding="utf-8")

        yield PreparedPythonProtocRun(
            working_directory=shadow_root,
            include_args=(f"-I{virtual_root}={shadow_root}",),
            proto_args=tuple(f"{virtual_root}/{import_path}" for import_path in selected_import_paths),
        )


def stage_python_protos(
    *,
    selected_import_paths: Sequence[str],
    proto_roots: Sequence[Path],
    virtual_root: str,
) -> dict[str, StagedPythonProto]:
    staged: dict[str, StagedPythonProto] = {}
    queue: deque[str] = deque(selected_import_paths)
    while queue:
        import_path = queue.popleft()
        if import_path in staged:
            continue

        source_path = resolve_local_proto(import_path, proto_roots)
        if source_path is None:
            raise FileNotFoundError(f"[grpc][python] staged proto not found in configured roots: {import_path}")

        source_text = source_path.read_text(encoding="utf-8")
        local_imports, rewritten = rewrite_local_imports(
            source_text,
            proto_roots=proto_roots,
            virtual_root=virtual_root,
        )
        staged[import_path] = StagedPythonProto(
            import_path=Path(import_path),
            source_path=source_path,
            contents=rewritten,
        )
        for dependency in local_imports:
            if dependency not in staged:
                queue.append(dependency)
    return staged


def rewrite_local_imports(
    source_text: str,
    *,
    proto_roots: Sequence[Path],
    virtual_root: str,
) -> tuple[tuple[str, ...], str]:
    local_imports: list[str] = []
    seen_imports: set[str] = set()
    prefixed_root = virtual_root + "/"

    def replace(match: re.Match[str]) -> str:
        raw_path = match.group("path")
        normalized_path = strip_virtual_root(raw_path, virtual_root)
        if normalized_path.startswith("google/protobuf/"):
            return match.group(0)

        if resolve_local_proto(normalized_path, proto_roots) is None:
            return match.group(0)

        if normalized_path not in seen_imports:
            seen_imports.add(normalized_path)
            local_imports.append(normalized_path)

        if raw_path.startswith(prefixed_root):
            return match.group(0)
        return f'{match.group("prefix")}"{prefixed_root}{normalized_path}"{match.group("suffix")}'

    rewritten = IMPORT_PATTERN.sub(replace, source_text)
    return tuple(local_imports), rewritten


def strip_virtual_root(import_path: str, virtual_root: str) -> str:
    prefixed_root = virtual_root + "/"
    if import_path.startswith(prefixed_root):
        return import_path[len(prefixed_root) :]
    return import_path


def resolve_local_proto(import_path: str, proto_roots: Sequence[Path]) -> Path | None:
    relative_path = Path(import_path)
    for root in proto_roots:
        candidate = (root / relative_path).resolve()
        if candidate.is_file():
            return candidate
    return None
