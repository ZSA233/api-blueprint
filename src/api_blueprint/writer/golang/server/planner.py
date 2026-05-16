from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .blueprint import GolangBlueprint, GolangRouterGroup
    from .writer import GolangWriter


@dataclass(frozen=True)
class GoServerBlueprintPlan:
    route_root_dir: Path
    binary_runtime_dir: Path
    http_root_dir: Path


@dataclass(frozen=True)
class GoServerRouteGroupPlan:
    group: "GolangRouterGroup"
    route_dir: Path
    binary_dir: Path
    http_dir: Path


def build_go_server_blueprint_plan(writer: "GolangWriter", bp: "GolangBlueprint") -> GoServerBlueprintPlan:
    return GoServerBlueprintPlan(
        route_root_dir=writer.working_dir / writer.views_package / "routes" / bp.root_package,
        binary_runtime_dir=writer.working_dir / writer.views_package / bp.binary_runtime_gen_path,
        http_root_dir=writer.http_transport_dir / bp.root_package,
    )


def build_go_server_route_group_plan(
    writer: "GolangWriter",
    bp: "GolangBlueprint",
    group: "GolangRouterGroup",
) -> GoServerRouteGroupPlan:
    bp_plan = build_go_server_blueprint_plan(writer, bp)
    route_dir = bp_plan.route_root_dir / group.package if group.branch else bp_plan.route_root_dir
    http_dir = bp_plan.http_root_dir / group.package if group.branch else bp_plan.http_root_dir
    return GoServerRouteGroupPlan(
        group=group,
        route_dir=route_dir,
        binary_dir=route_dir / group.binary_gen_path,
        http_dir=http_dir,
    )
