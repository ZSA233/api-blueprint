from __future__ import annotations

import re

from api_blueprint.contract import ContractGraph
from api_blueprint.writer.core.templates import render
from api_blueprint.writer.grpc.planner import plan_proto_files


def render_proto_files(
    graph: ContractGraph,
    *,
    package: str,
    go_package_prefix: str,
) -> dict[str, str]:
    plans = plan_proto_files(graph, package=package, go_package_prefix=go_package_prefix)
    return {
        path: _normalize_proto_text(render("grpc", "proto.proto", {"file": file_plan}))
        for path, file_plan in plans.items()
    }


def _normalize_proto_text(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.rstrip()) + "\n"
