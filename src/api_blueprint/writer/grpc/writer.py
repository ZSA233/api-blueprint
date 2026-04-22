from __future__ import annotations

import logging
from typing import Sequence

from api_blueprint.config import ResolvedGrpcConfig, ResolvedGrpcJobConfig, ResolvedGrpcTargetConfig

from .models import GrpcGenerationJob
from .planner import expand_job, expand_target
from .selection import select_jobs, select_targets
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

    def list_targets(self, patterns: Sequence[str] = ()) -> tuple[ResolvedGrpcTargetConfig, ...]:
        return select_targets(self.config.targets, patterns)

    def plan_jobs(self, patterns: Sequence[str] = ()) -> tuple[GrpcGenerationJob, ...]:
        jobs = self.list_jobs(patterns)
        return tuple(
            expand_job(job, global_include_paths=self.config.include_paths)
            for job in jobs
        )

    def plan_targets(self, patterns: Sequence[str] = ()) -> tuple[GrpcGenerationJob, ...]:
        targets = self.list_targets(patterns)
        return tuple(
            expand_target(target, global_import_roots=self.config.import_roots)
            for target in targets
        )

    def explain_target(self, target_id: str) -> GrpcGenerationJob:
        matched = self.list_targets((target_id,))
        if len(matched) != 1:
            raise ValueError(
                f"[gen_grpc] --explain-target 需要唯一 target id，当前匹配到 {len(matched)} 个 target: {target_id}"
            )
        return expand_target(matched[0], global_import_roots=self.config.import_roots)

    def plan(
        self,
        *,
        target_patterns: Sequence[str] = (),
        job_patterns: Sequence[str] = (),
    ) -> tuple[GrpcGenerationJob, ...]:
        planned: list[GrpcGenerationJob] = []
        if target_patterns or not job_patterns:
            planned.extend(self.plan_targets(target_patterns))
        if job_patterns or not target_patterns:
            planned.extend(self.plan_jobs(job_patterns))
        return tuple(planned)

    def gen(
        self,
        *,
        target_patterns: Sequence[str] = (),
        job_patterns: Sequence[str] = (),
    ) -> tuple[GrpcGenerationJob, ...]:
        planned = self.plan(target_patterns=target_patterns, job_patterns=job_patterns)
        for job in planned:
            self.toolchain.run(job)
        return planned
