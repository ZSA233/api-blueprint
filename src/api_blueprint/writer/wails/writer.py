from __future__ import annotations

from typing import Sequence

from api_blueprint.config import ResolvedWailsConfig, ResolvedWailsTargetConfig
from api_blueprint.engine import Blueprint
from api_blueprint.writer.typescript.writer import TypeScriptWriter

from .golang import WailsGoWriter
from .models import WailsGenerationTarget
from .selection import select_targets


class WailsWriter:
    def __init__(self, config: ResolvedWailsConfig):
        self.config = config

    def list_targets(self, patterns: Sequence[str] = ()) -> tuple[ResolvedWailsTargetConfig, ...]:
        return select_targets(self.config.targets, patterns)

    def explain_target(self, target_id: str) -> WailsGenerationTarget:
        matched = self.list_targets((target_id,))
        if len(matched) != 1:
            raise ValueError(f"[gen_wails] --explain-target 需要唯一 target id，当前匹配到 {len(matched)} 个 target: {target_id}")
        target = matched[0]
        return WailsGenerationTarget(
            id=target.id,
            version=target.version,
            go_out_dir=target.go_out_dir,
            typescript_out_dir=target.typescript_out_dir,
        )

    def gen(
        self,
        entrypoints: list[Blueprint],
        *,
        target_patterns: Sequence[str] = (),
    ) -> tuple[WailsGenerationTarget, ...]:
        planned = tuple(
            WailsGenerationTarget(
                id=target.id,
                version=target.version,
                go_out_dir=target.go_out_dir,
                typescript_out_dir=target.typescript_out_dir,
            )
            for target in self.list_targets(target_patterns)
        )
        for target in planned:
            target.go_out_dir.mkdir(parents=True, exist_ok=True)
            target.typescript_out_dir.mkdir(parents=True, exist_ok=True)
            go_writer = WailsGoWriter(target.go_out_dir, version=target.version)
            go_writer.register(*entrypoints)
            go_writer.gen()

            ts_writer = TypeScriptWriter(
                target.typescript_out_dir,
                template_lang="typescript",
                transport_kind=f"wails-{target.version}",
                allow_raw_ws=False,
            )
            ts_writer.register(*entrypoints)
            ts_writer.gen()
        return planned
