from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Sequence

from api_blueprint.contract import ContractGraph
from api_blueprint.route_selection import normalize_selection_rules
from api_blueprint.writer.grpc.layout import GrpcProtoFileRule
from api_blueprint.writer.core.templates import render
from api_blueprint.writer.grpc.planner import plan_proto_files

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("GrpcProtoWriter")
logger.setLevel(logging.INFO)


def render_proto_files(
    graph: ContractGraph,
    *,
    package: str,
    go_package_prefix: str,
    proto_files: Sequence[GrpcProtoFileRule] = (),
    include: Sequence[str] = (),
    exclude: Sequence[str] = (),
) -> dict[str, str]:
    plans = plan_proto_files(
        graph,
        package=package,
        go_package_prefix=go_package_prefix,
        proto_files=proto_files,
        include=normalize_selection_rules(include),
        exclude=normalize_selection_rules(exclude),
    )
    return {
        path: _normalize_proto_text(render("grpc", "gen_proto.proto", {"file": file_plan}))
        for path, file_plan in plans.items()
    }


def write_proto_files(out_dir: Path, files: dict[str, str]) -> None:
    for relative, text in sorted(files.items()):
        file_path = out_dir / relative
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(text, encoding="utf-8")
        logger.info("[+] Written: %s", file_path)


def _normalize_proto_text(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.rstrip()) + "\n"
