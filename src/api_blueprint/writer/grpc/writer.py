from __future__ import annotations

import logging
from typing import Sequence

from api_blueprint.config import ResolvedGrpcConfig, ResolvedGrpcJobConfig

from .models import GrpcGenerationJob
from .selection import expand_job, select_jobs
from .toolchain import GrpcToolchain


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("GrpcWriter")
logger.setLevel(logging.INFO)


class GrpcWriter:
    def __init__(self, config: ResolvedGrpcConfig, *, toolchain: GrpcToolchain | None = None):
        self.config = config
        self.toolchain = toolchain or GrpcToolchain(logger)

    def list_jobs(self, patterns: Sequence[str] = ()) -> tuple[ResolvedGrpcJobConfig, ...]:
        return select_jobs(self.config.jobs, patterns)

    def plan_jobs(self, patterns: Sequence[str] = ()) -> tuple[GrpcGenerationJob, ...]:
        jobs = self.list_jobs(patterns)
        return tuple(
            expand_job(job, proto_root=self.config.proto_root, global_include_paths=self.config.include_paths)
            for job in jobs
        )

    def gen(self, patterns: Sequence[str] = ()) -> tuple[GrpcGenerationJob, ...]:
        planned = self.plan_jobs(patterns)
        for job in planned:
            self.toolchain.run(job)
        return planned
