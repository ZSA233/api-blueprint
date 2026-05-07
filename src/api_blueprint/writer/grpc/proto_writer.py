from __future__ import annotations

import re
from typing import Sequence

from api_blueprint.contract import ContractGraph
from api_blueprint.writer.grpc.layout import GrpcProtoFileRule
from api_blueprint.writer.core.templates import render
from api_blueprint.writer.grpc.planner import plan_proto_files


def render_proto_files(
    graph: ContractGraph,
    *,
    package: str,
    go_package_prefix: str,
    proto_files: Sequence[GrpcProtoFileRule] = (),
) -> dict[str, str]:
    plans = plan_proto_files(
        graph,
        package=package,
        go_package_prefix=go_package_prefix,
        proto_files=proto_files,
    )
    return {
        path: _normalize_proto_text(render("grpc", "proto.proto", {"file": file_plan}))
        for path, file_plan in plans.items()
    }


def _normalize_proto_text(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.rstrip()) + "\n"
