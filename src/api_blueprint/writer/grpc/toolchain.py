from __future__ import annotations

import logging
import os
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from .models import GrpcGenerationJob


logger = logging.getLogger("GrpcWriter")
logger.setLevel(logging.INFO)


class GrpcToolchain:
    def __init__(self, grpc_logger: logging.Logger | None = None):
        self.logger = grpc_logger or logger

    def run(self, job: GrpcGenerationJob) -> None:
        if job.preset == "go":
            self.run_go(job)
            return
        if job.preset == "python":
            self.run_python(job)
            return
        raise ValueError(f"[gen_grpc] 不支持的gRPC preset: {job.preset}")

    def build_go_command(self, job: GrpcGenerationJob) -> list[str]:
        return [
            "protoc",
            *self._include_args(job),
            *self._go_plugin_args("go", job),
            *self._go_plugin_args("go-grpc", job),
            *self._proto_args(job),
        ]

    def build_python_args(self, job: GrpcGenerationJob, *, wkt_dir: Path) -> list[str]:
        return [
            "grpc_tools.protoc",
            *self._include_args(job),
            f"-I{wkt_dir}",
            f"--python_out={job.output}",
            f"--grpc_python_out={job.output}",
            f"--pyi_out={job.output}",
            *self._proto_args(job),
        ]

    def run_go(self, job: GrpcGenerationJob) -> None:
        self._require_executables("protoc", "protoc-gen-go", "protoc-gen-go-grpc")
        job.output.mkdir(parents=True, exist_ok=True)
        command = self.build_go_command(job)
        self.logger.info("[grpc][go] %s -> %s", job.name, job.output)
        subprocess.run(command, cwd=job.proto_root, check=True)

    def run_python(self, job: GrpcGenerationJob) -> None:
        protoc, wkt_dir = self.load_grpc_tools()
        job.output.mkdir(parents=True, exist_ok=True)
        args = self.build_python_args(job, wkt_dir=wkt_dir)
        self.logger.info("[grpc][python] %s -> %s", job.name, job.output)
        with working_directory(job.proto_root):
            code = protoc.main(args)
        if code != 0:
            raise RuntimeError(f"[grpc][python] job[{job.name}] grpc_tools.protoc exited with status {code}")

    def load_grpc_tools(self) -> tuple[Any, Path]:
        try:
            import grpc_tools
            from grpc_tools import protoc
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "[grpc][python] Python gRPC generation requires grpcio-tools; install `grpcio-tools` and retry."
            ) from exc
        return protoc, Path(grpc_tools.__file__).resolve().parent / "_proto"

    def _require_executables(self, *names: str) -> None:
        missing = [name for name in names if shutil.which(name) is None]
        if missing:
            raise FileNotFoundError(f"[grpc][go] 缺少必要可执行文件: {', '.join(missing)}")

    def _include_args(self, job: GrpcGenerationJob) -> list[str]:
        return [
            f"-I{job.proto_root}",
            *(f"-I{path}" for path in job.include_paths),
        ]

    def _go_plugin_args(self, plugin: str, job: GrpcGenerationJob) -> list[str]:
        args = [f"--{plugin}_out={job.output}", f"--{plugin}_opt=paths={self._go_paths_mode(job)}"]
        if job.layout == "go_package" and job.module is not None:
            args.append(f"--{plugin}_opt=module={job.module}")
        return args

    def _go_paths_mode(self, job: GrpcGenerationJob) -> str:
        if job.layout == "source_relative":
            return "source_relative"
        if job.layout == "go_package":
            return "import"
        raise ValueError(f"[gen_grpc] 不支持的gRPC Go layout: {job.layout}")

    def _proto_args(self, job: GrpcGenerationJob) -> list[str]:
        return [path.as_posix() for path in job.proto_files]


@contextmanager
def working_directory(path: Path) -> Generator[None, None, None]:
    current = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(current)
