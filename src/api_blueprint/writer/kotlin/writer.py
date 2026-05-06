from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import IO, TYPE_CHECKING, Generator, Optional, Sequence

from api_blueprint.engine.router import Router
from api_blueprint.writer.core.base import BaseWriter
from api_blueprint.writer.core.contract_adapters import RouteContractIndex, RouteProtocolContract
from api_blueprint.writer.core.files import ensure_filepath_open
from api_blueprint.writer.core.templates import render

from .blueprint import KotlinBlueprint
from .naming import to_package_path
from .selection import normalize_rules


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("KotlinWriter")
logger.setLevel(logging.INFO)

if TYPE_CHECKING:
    from api_blueprint.contract import ContractGraph


class KotlinWriter(BaseWriter[KotlinBlueprint]):
    def __init__(
        self,
        working_dir: str | Path = ".",
        *,
        package: str,
        base_url: str | None = None,
        base_url_expr: str | None = None,
        include: Sequence[str] = (),
        exclude: Sequence[str] = (),
        allow_empty: bool = False,
        contract_graph: ContractGraph | None = None,
    ):
        super().__init__(working_dir)
        self.package = package
        self.package_path = to_package_path(package)
        self.base_url = base_url or ""
        self.base_url_expr = base_url_expr
        self.rendered_base_url = base_url_expr if base_url_expr is not None else json.dumps(self.base_url)
        self.include = normalize_rules(include)
        self.exclude = normalize_rules(exclude)
        self.allow_empty = allow_empty
        self.route_contract_index = RouteContractIndex.from_graph(contract_graph) if contract_graph is not None else None

    @property
    def package_dir(self) -> Path:
        return self.working_dir / self.package_path

    def gen(self) -> None:
        total_routes = 0
        for bp in self.bps:
            bp.build()
            bp.collect()
            total_routes += len(bp.routes)
            if not bp.routes:
                continue
            self._gen_blueprint(bp)
        if total_routes == 0 and not self.allow_empty:
            raise ValueError("[kotlin-client] Kotlin include/exclude 过滤后没有可生成的 route")

    def _ensure_route_contract_index(self) -> RouteContractIndex:
        if self.route_contract_index is None:
            from api_blueprint.contract import build_contract_graph

            self.route_contract_index = RouteContractIndex.from_graph(build_contract_graph([bp.bp for bp in self.bps]))
        return self.route_contract_index

    def route_protocol_for(self, router: Router) -> RouteProtocolContract:
        return self._ensure_route_contract_index().protocol_for_router(router)

    def _gen_blueprint(self, bp: KotlinBlueprint) -> None:
        base_dir = self.package_dir
        internal_dir = base_dir / "internal"
        endpoints_dir = base_dir / "endpoints"
        models_dir = base_dir / "models"
        for path in (internal_dir, endpoints_dir, models_dir):
            path.mkdir(parents=True, exist_ok=True)

        context = {"writer": self, "bp": bp}
        for name in ["ApiConfig.kt", "ApiException.kt", "ApiClient.kt"]:
            with self.write_file(base_dir / name, overwrite=True) as handle:
                if handle:
                    handle.write(render("kotlin", name, context))

        for name in ["HttpExecutor.kt", "UrlBuilder.kt"]:
            with self.write_file(internal_dir / name, overwrite=True) as handle:
                if handle:
                    handle.write(render("kotlin", name, context, "internal"))

        shared_protos = bp.registry.filter(module="shared")
        if shared_protos:
            with self.write_file(models_dir / "Models.kt", overwrite=True) as handle:
                if handle:
                    handle.write(
                        render("kotlin", "Models.kt", {**context, "protos": shared_protos}, "models")
                    )

        for group in bp.groups.values():
            group_protos = bp.registry.filter(module=group.slug)
            if group_protos:
                group_models_context = {**context, "group": group, "protos": group_protos}
                with self.write_file(
                    models_dir / f"{group.class_name}Models.kt", overwrite=True
                ) as handle:
                    if handle:
                        handle.write(
                            render("kotlin", "GroupModels.kt", group_models_context, "models")
                        )

            with self.write_file(endpoints_dir / f"{group.class_name}.kt", overwrite=True) as handle:
                if handle:
                    handle.write(render("kotlin", "ApiGroup.kt", {**context, "group": group}, "endpoints"))

    @contextmanager
    def write_file(self, filepath: str | Path, overwrite: bool = False) -> Generator[Optional[IO], None, None]:
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
