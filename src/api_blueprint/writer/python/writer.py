from __future__ import annotations

import json
import logging
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import IO, TYPE_CHECKING, Generator, Sequence

from api_blueprint.engine.connection import ConnectionKind
from api_blueprint.engine.router import Router
from api_blueprint.route_selection import normalize_selection_rules
from api_blueprint.writer.core.base import BaseWriter
from api_blueprint.writer.core.contract_adapters import RouteContractIndex, RouteProtocolContract
from api_blueprint.writer.core.files import ensure_filepath_open
from api_blueprint.writer.core.planning import route_matches_rule
from api_blueprint.writer.core.templates import render

from .blueprint import PythonBlueprint
from .naming import to_package_segments
from .planner import build_python_blueprint_plan

if TYPE_CHECKING:
    from api_blueprint.contract import ContractGraph
    from .planner import PythonRouteGroupPlan


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("PythonWriter")
logger.setLevel(logging.INFO)


class PythonBaseWriter(BaseWriter[PythonBlueprint]):
    runtime_template: str
    route_template: str
    transport_template: str
    target_label: str

    def __init__(
        self,
        working_dir: str | Path = ".",
        *,
        python_package_root: str | None = None,
        base_url: str | None = None,
        base_url_expr: str | None = None,
        include: Sequence[str] = (),
        exclude: Sequence[str] = (),
        contract_graph: "ContractGraph | None" = None,
    ):
        super().__init__(working_dir)
        self.package_segments = to_package_segments(python_package_root)
        self.base_url = base_url or ""
        self.base_url_expr = base_url_expr
        self.rendered_base_url = base_url_expr if base_url_expr is not None else json.dumps(self.base_url)
        self.include = normalize_selection_rules(include)
        self.exclude = normalize_selection_rules(exclude)
        self.route_contract_index = RouteContractIndex.from_graph(contract_graph) if contract_graph is not None else None

    @property
    def package_dir(self) -> Path:
        path = self.working_dir
        for segment in self.package_segments:
            path /= segment
        return path

    def gen(self) -> None:
        for bp in self.bps:
            bp.build()
            bp.collect()
            self._gen_blueprint(bp)

    def route_protocol_for(self, router: Router) -> RouteProtocolContract:
        return self._ensure_route_contract_index().protocol_for_router(router)

    def route_selected(self, router: Router, protocol: RouteProtocolContract) -> bool:
        route = _route_manifest(router, protocol)
        if self.include and not any(route_matches_rule(route, rule) for rule in self.include):
            return False
        return not any(route_matches_rule(route, rule) for rule in self.exclude)

    def _ensure_route_contract_index(self) -> RouteContractIndex:
        if self.route_contract_index is None:
            from api_blueprint.contract import build_contract_graph

            self.route_contract_index = RouteContractIndex.from_graph(build_contract_graph([bp.bp for bp in self.bps]))
        return self.route_contract_index

    def _gen_blueprint(self, bp: PythonBlueprint) -> None:
        context = {"writer": self, "bp": bp}
        plan = build_python_blueprint_plan(self, bp)

        self._ensure_package_markers(self.package_dir)
        self._ensure_package_markers(plan.root_directory)
        self._ensure_package_markers(plan.runtime.directory)
        self._ensure_package_markers(plan.routes_directory)
        self._ensure_package_markers(plan.transports_directory)
        self._ensure_package_markers(plan.http_transport.directory)

        with self.write_file(plan.runtime.public_file, overwrite=False) as handle:
            if handle:
                handle.write(f"from .{self.runtime_template.removesuffix('.py')} import *\n")
        with self.write_file(plan.runtime.generated_file, overwrite=True) as handle:
            if handle:
                handle.write(_render_python(self.runtime_template, context, "runtime"))

        for group_plan in plan.route_groups:
            self._gen_group(group_plan)

        with self.write_file(plan.http_transport.public_file, overwrite=False) as handle:
            if handle:
                handle.write(f"from .{self.transport_template.removesuffix('.py')} import *\n")
        with self.write_file(plan.http_transport.generated_file, overwrite=True) as handle:
            if handle:
                handle.write(_render_python(self.transport_template, context, "transports/http"))

    def root_dir(self, bp: PythonBlueprint) -> Path:
        root_dir = self.package_dir
        for segment in bp.root_segments:
            root_dir /= segment
        return root_dir

    def _gen_group(self, group_plan: "PythonRouteGroupPlan") -> None:
        self._ensure_package_tree(group_plan.directory)
        self._migrate_legacy_public_file(group_plan)
        with self.write_file(group_plan.public_file, overwrite=False) as handle:
            if handle:
                handle.write(self._default_public_import())
        with self.write_file(group_plan.generated_file, overwrite=True) as handle:
            if handle:
                handle.write(_render_python(self.route_template, {"group": group_plan.group}, "routes"))
        self._cleanup_legacy_route_dir(group_plan)

    def _migrate_legacy_public_file(self, group_plan: "PythonRouteGroupPlan") -> None:
        legacy_file = group_plan.legacy_public_file
        if group_plan.public_file.exists() or legacy_file == group_plan.public_file or not legacy_file.is_file():
            return
        group_plan.public_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_file, group_plan.public_file)
        logger.info("[>] Migrated: %s -> %s", legacy_file, group_plan.public_file)

    def _cleanup_legacy_route_dir(self, group_plan: "PythonRouteGroupPlan") -> None:
        legacy_dir = group_plan.legacy_public_file.parent
        if legacy_dir == group_plan.directory or not legacy_dir.is_dir():
            return
        if self._is_default_only_legacy_route_dir(legacy_dir):
            shutil.rmtree(legacy_dir)
            logger.info("[-] Removed stale legacy route dir: %s", legacy_dir)

    def _is_default_only_legacy_route_dir(self, legacy_dir: Path) -> bool:
        public_name = self.route_template.replace("gen_", "")
        allowed_files = {"__init__.py", self.route_template, public_name}
        for path in legacy_dir.iterdir():
            if path.name == "__pycache__" and path.is_dir():
                continue
            if path.is_dir() or path.name not in allowed_files:
                return False
            if path.name == public_name and path.read_text(encoding="utf-8") != self._default_public_import():
                return False
        return True

    def _default_public_import(self) -> str:
        return f"from .{self.route_template.removesuffix('.py')} import *\n"

    def _ensure_package_tree(self, package_dir: Path) -> None:
        package_dirs: list[Path] = []
        current = package_dir
        while True:
            package_dirs.append(current)
            if current == self.package_dir or current.parent == current:
                break
            current = current.parent
        for current in reversed(package_dirs):
            self._ensure_package_markers(current)

    def _ensure_package_markers(self, package_dir: Path) -> None:
        with self.write_file(package_dir / "__init__.py", overwrite=False) as handle:
            if handle:
                handle.write(f'"""Generated package for api-blueprint {self.target_label} artifacts."""\n')

    @contextmanager
    def write_file(self, filepath: str | Path, overwrite: bool = False) -> Generator[IO[str] | None, None, None]:
        filepath_str = str(filepath)
        wrote = False
        with ensure_filepath_open(filepath_str, "w", overwrite=overwrite) as handle:
            if handle:
                wrote = True
            yield handle
        if wrote:
            logger.info("[+] Written: %s", filepath_str)
        else:
            logger.info("[.] Skipped: %s", filepath_str)


class PythonClientWriter(PythonBaseWriter):
    runtime_template = "gen_client.py"
    route_template = "gen_client.py"
    transport_template = "gen_client.py"
    target_label = "Python client"


class PythonServerWriter(PythonBaseWriter):
    runtime_template = "gen_server.py"
    route_template = "gen_service.py"
    transport_template = "gen_server.py"
    target_label = "Python server"


def _route_manifest(router: Router, protocol: RouteProtocolContract) -> dict[str, object]:
    root = router.group.root.strip("/") or "root"
    group = router.group.branch.strip("/") or root
    kind = "rpc" if router.connection_kind == ConnectionKind.RPC else router.connection_kind.value
    return {
        "id": protocol.route.route_id,
        "service_id": f"{root}.{group}",
        "kind": kind,
        "operation": protocol.route.func_name,
        "methods": list(protocol.route.http_methods or router.methods),
        "url": protocol.route.url,
        "tags": list(router.tags),
    }


def _render_python(name: str, context: dict[str, object], relative_path: str) -> str:
    return _normalize_python_blank_lines(render("python", name, context, relative_path))


def _normalize_python_blank_lines(source: str) -> str:
    output: list[str] = []
    blank_count = 0
    paren_depth = 0
    lines = source.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            next_line = _next_nonblank_line(lines, index + 1)
            if paren_depth > 0:
                continue
            if _should_drop_indented_blank(output, next_line):
                continue
            blank_count += 1
            next_indent = _indent_width(next_line) if next_line is not None else 0
            max_blank_count = 1 if next_indent > 0 else 2
            if blank_count <= max_blank_count:
                output.append("")
            continue

        if _has_blank_after_block_header(output, line):
            output.pop()
        output.append(line.rstrip())
        blank_count = 0
        paren_depth = max(0, paren_depth + line.count("(") - line.count(")"))

    while output and output[-1] == "":
        output.pop()
    return "\n".join(output) + "\n"


def _has_blank_after_block_header(output: list[str], next_line: str) -> bool:
    if len(output) < 2 or output[-1] != "":
        return False
    previous = output[-2]
    if not previous.rstrip().endswith(":"):
        return False
    previous_indent = _indent_width(previous)
    next_indent = _indent_width(next_line)
    return next_indent > previous_indent


def _should_drop_indented_blank(output: list[str], next_line: str | None) -> bool:
    if next_line is None or not output:
        return False
    next_indent = _indent_width(next_line)
    if next_indent == 0:
        return False
    next_stripped = next_line.strip()
    previous = output[-1]
    if previous.lstrip().startswith("@") and next_stripped.startswith(("def ", "async def ")):
        return True
    if next_stripped.startswith(("@", "def ", "async def ", "class ")):
        return False
    if previous == "":
        return False
    previous_indent = _indent_width(previous)
    return previous_indent <= next_indent


def _next_nonblank_line(lines: list[str], start: int) -> str | None:
    for line in lines[start:]:
        if line.strip():
            return line
    return None


def _indent_width(line: str | None) -> int:
    if line is None:
        return 0
    return len(line) - len(line.lstrip(" "))
