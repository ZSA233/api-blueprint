from __future__ import annotations

import json
import logging
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import IO, TYPE_CHECKING, Mapping, Sequence, Set, Union

from api_blueprint.engine.router import Router
from api_blueprint.route_selection import normalize_selection_rules
from api_blueprint.writer.core.base import BaseWriter
from api_blueprint.writer.core.contract_adapters import RouteContractIndex, RouteProtocolContract
from api_blueprint.writer.core.contracts import RouteContract
from api_blueprint.writer.core.errors import (
    ApiErrorEntry,
    ApiErrorGroup,
    api_errors_from_manifest,
    group_api_errors,
    route_api_errors_from_manifest,
)
from api_blueprint.writer.core.files import ensure_filepath_open

from .blueprint import TypeScriptBlueprint

if TYPE_CHECKING:
    from api_blueprint.contract import ContractGraph


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("TypeScriptWriter")
logger.setLevel(logging.INFO)


class TypeScriptWriter(BaseWriter[TypeScriptBlueprint]):
    RUNTIME_DIR_NAME = "runtime"
    ROUTES_DIR_NAME = "routes"
    TRANSPORTS_DIR_NAME = "transports"

    def __init__(
        self,
        working_dir: Union[str, Path] = ".",
        *,
        base_url: str | None = None,
        base_url_expr: str | None = None,
        template_lang: str = "typescript",
        transport_kind: str = "http",
        transport_class_name: str = "DefaultTransport",
        allow_raw_ws: bool = True,
        emit_http_facade: bool = True,
        overlay_name: str | None = None,
        frontend_mode: str = "external",
        include: Sequence[str] = (),
        exclude: Sequence[str] = (),
        wails_binding_manifest: Mapping[str, str] | None = None,
        contract_graph: ContractGraph | None = None,
    ):
        super().__init__(working_dir)
        self.base_url = base_url or ""
        self.base_url_expr = base_url_expr
        self.rendered_base_url = base_url_expr if base_url_expr is not None else json.dumps(self.base_url)
        self.template_lang = template_lang
        self.transport_kind = transport_kind
        self.transport_class_name = transport_class_name
        self.allow_raw_ws = allow_raw_ws
        self.emit_http_facade = emit_http_facade
        self.overlay_name = overlay_name
        self.frontend_mode = frontend_mode
        self.include = normalize_selection_rules(include)
        self.exclude = normalize_selection_rules(exclude)
        self.wails_binding_manifest = dict(wails_binding_manifest or {})
        self.contract_graph = contract_graph
        self.route_contract_index = RouteContractIndex.from_graph(contract_graph) if contract_graph is not None else None
        self._written_files: Set[str] = set()

    @property
    def runtime_dir_name(self) -> str:
        return self.RUNTIME_DIR_NAME

    @property
    def routes_dir_name(self) -> str:
        return self.ROUTES_DIR_NAME

    @property
    def transports_dir_name(self) -> str:
        return self.TRANSPORTS_DIR_NAME

    @property
    def overlay_dir_name(self) -> str:
        if self.overlay_name is None:
            raise RuntimeError("overlay_name is required for overlay directory derivation")
        return self.overlay_name

    def gen(self) -> None:
        self.cleanup_legacy_layout()
        for bp in self.bps:
            bp.build()
            bp.gen()

    def _ensure_route_contract_index(self) -> RouteContractIndex:
        if self.route_contract_index is None:
            from api_blueprint.contract import build_contract_graph

            self.contract_graph = build_contract_graph([bp.bp for bp in self.bps])
            self.route_contract_index = RouteContractIndex.from_graph(self.contract_graph)
        return self.route_contract_index

    def api_errors(self) -> tuple[ApiErrorEntry, ...]:
        if self.contract_graph is None:
            from api_blueprint.contract import build_contract_graph

            self.contract_graph = build_contract_graph([bp.bp for bp in self.bps])
            if self.route_contract_index is None:
                self.route_contract_index = RouteContractIndex.from_graph(self.contract_graph)
        return api_errors_from_manifest(self.contract_graph.to_manifest())

    def api_error_groups(self) -> tuple[ApiErrorGroup, ...]:
        return group_api_errors(self.api_errors())

    def api_errors_for_bp(self, bp: TypeScriptBlueprint) -> tuple[ApiErrorEntry, ...]:
        if self.contract_graph is None:
            self._ensure_route_contract_index()
        route_ids = [route.contract.route_id for route in bp.routes]
        return api_errors_from_manifest(self.contract_graph.to_manifest(), route_ids=route_ids)

    def api_error_groups_for_bp(self, bp: TypeScriptBlueprint) -> tuple[ApiErrorGroup, ...]:
        return group_api_errors(self.api_errors_for_bp(bp))

    def route_api_errors_for_bp(self, bp: TypeScriptBlueprint) -> dict[str, tuple[ApiErrorEntry, ...]]:
        if self.contract_graph is None:
            self._ensure_route_contract_index()
        route_ids = [route.contract.route_id for route in bp.routes]
        return route_api_errors_from_manifest(self.contract_graph.to_manifest(), route_ids=route_ids)

    def route_contract_for(self, router: Router) -> RouteContract:
        return self._ensure_route_contract_index().protocol_for_router(router).route

    def route_protocol_for(self, router: Router) -> RouteProtocolContract:
        return self._ensure_route_contract_index().protocol_for_router(router)

    def cleanup_legacy_layout(self) -> None:
        for bp in self.bps:
            root_dir = self.working_dir / bp.package
            if not root_dir.exists():
                continue
            for legacy_dir in sorted(root_dir.rglob("(*)"), key=lambda path: len(path.parts), reverse=True):
                if legacy_dir.is_dir():
                    shutil.rmtree(legacy_dir)

    @contextmanager
    def write_file(self, filepath: Union[str, Path], overwrite: bool = False):
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
