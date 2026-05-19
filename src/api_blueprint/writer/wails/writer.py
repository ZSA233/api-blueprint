from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from api_blueprint.config import ResolvedTargetConfig, ResolvedWailsConfig, ResolvedWailsTargetConfig
from api_blueprint.contract import build_contract_graph
from api_blueprint.engine import Blueprint
from api_blueprint.engine.utils import join_path_imports
from api_blueprint.writer.core.contract_adapters import RouteContractIndex
from api_blueprint.writer.core.go_naming import to_go_package_path
from api_blueprint.writer.typescript.writer import TypeScriptWriter

from .golang import WailsGoWriter
from .models import WailsGenerationTarget
from .selection import WailsRouteSelection, select_targets

if TYPE_CHECKING:
    from api_blueprint.contract import ContractGraph


class WailsWriter:
    def __init__(self, config: ResolvedWailsConfig, *, contract_graph: ContractGraph | None = None):
        self.config = config
        self.contract_graph = contract_graph
        self.route_contract_index = RouteContractIndex.from_graph(contract_graph) if contract_graph is not None else None

    def list_targets(self, patterns: Sequence[str] = ()) -> tuple[ResolvedWailsTargetConfig, ...]:
        return select_targets(self.config.targets, patterns)

    def _build_plan(
        self,
        target: ResolvedWailsTargetConfig,
        *,
        shared_go_output: Path,
        shared_ts_output: Path,
    ) -> WailsGenerationTarget:
        overlay_name = target.overlay_name
        go_root = shared_go_output.resolve()
        ts_root = shared_ts_output.resolve()
        return WailsGenerationTarget(
            id=target.id,
            version=target.version,
            overlay_name=overlay_name,
            frontend_mode=target.frontend_mode,
            include=target.include,
            exclude=target.exclude,
            go_transport_dir=(go_root / "transports" / overlay_name).resolve(),
            go_service_pattern=f"{(go_root / 'transports' / overlay_name).as_posix()}/<blueprint-root>/<group...>",
            go_route_overlay_pattern=f"{(go_root / 'transports' / overlay_name).as_posix()}/<blueprint-root>/<group...>",
            typescript_route_overlay_pattern=(
                None
                if target.frontend_mode == "none"
                else f"{ts_root.as_posix()}/<blueprint-root>/transports/{overlay_name}/<blueprint-root>/<group...>"
            ),
            typescript_transport_pattern=(
                None
                if target.frontend_mode == "none"
                else f"{ts_root.as_posix()}/<blueprint-root>/transports/{overlay_name}/transport.ts"
            ),
        )

    def explain_target(
        self,
        target_id: str,
        *,
        golang_config: ResolvedTargetConfig,
        typescript_config: ResolvedTargetConfig,
    ) -> WailsGenerationTarget:
        matched = self.list_targets((target_id,))
        if len(matched) != 1:
            raise ValueError(
                f"[api-gen explain-target] 需要唯一 target id，当前匹配到 {len(matched)} 个 target: {target_id}"
            )
        target = matched[0]
        shared_go_output = golang_config.output
        shared_ts_output = typescript_config.output
        if shared_go_output is None or shared_ts_output is None:
            raise ValueError("[api-gen explain-target] wails-transport 需要已解析的 server/client 输出路径")
        return self._build_plan(target, shared_go_output=shared_go_output, shared_ts_output=shared_ts_output)

    def _selection_for_target(self, target: ResolvedWailsTargetConfig) -> WailsRouteSelection:
        return WailsRouteSelection(include=target.include, exclude=target.exclude)

    def _ensure_route_contract_index(self, entrypoints: list[Blueprint]) -> RouteContractIndex:
        if self.route_contract_index is None:
            graph = self.contract_graph or build_contract_graph(entrypoints)
            self.route_contract_index = RouteContractIndex.from_graph(graph)
        return self.route_contract_index

    def _count_selected_routes(self, entrypoints: list[Blueprint], target: ResolvedWailsTargetConfig) -> int:
        selection = self._selection_for_target(target)
        route_contract_index = self._ensure_route_contract_index(entrypoints)
        count = 0
        for blueprint in entrypoints:
            for _group, router in blueprint.iter_router():
                route_name = route_contract_index.protocol_for_router(router).route.func_name
                if selection.includes_route(router, route_name=route_name):
                    count += 1
        return count

    def _build_wails_v3_binding_manifest(
        self,
        entrypoints: list[Blueprint],
        *,
        target: ResolvedWailsTargetConfig,
        go_writer: WailsGoWriter,
        selection: WailsRouteSelection,
    ) -> dict[str, str]:
        if target.version != "v3":
            return {}

        manifest: dict[str, str] = {}
        for blueprint in entrypoints:
            raw_root = blueprint.root.strip("/")
            if not raw_root:
                continue
            root_package = to_go_package_path(raw_root, fallback="root")
            for group, router in blueprint.iter_router():
                contract = go_writer.route_protocol_for(router).route
                if not selection.includes_route(router, route_name=contract.func_name):
                    continue
                branch = group.branch.strip("/")
                branch_package = to_go_package_path(branch, fallback="root") if branch else ""
                binding_import = join_path_imports(
                    go_writer.shared_views_imports,
                    "transports",
                    go_writer.overlay_dir_name,
                    root_package,
                    branch_package,
                )

                def add_method(method_name: str) -> None:
                    key = f"{contract.namespace}.{contract.service_name}.{method_name}"
                    manifest[key] = f"{binding_import}.{contract.service_name}.{method_name}"

                if contract.stream is not None:
                    add_method(contract.stream.connect_method)
                    add_method(contract.stream.close_method)
                elif contract.channel is not None:
                    add_method(contract.channel.connect_method)
                    if contract.channel.send_method is not None:
                        add_method(contract.channel.send_method)
                    add_method(contract.channel.close_method)
                else:
                    add_method(contract.func_name)
        return manifest

    def gen(
        self,
        entrypoints: list[Blueprint],
        *,
        golang_config: ResolvedTargetConfig,
        typescript_config: ResolvedTargetConfig,
        target_patterns: Sequence[str] = (),
    ) -> tuple[WailsGenerationTarget, ...]:
        shared_go_output = golang_config.output
        shared_ts_output = typescript_config.output
        if shared_go_output is None:
            raise ValueError("[api-gen wails-transport] 共享 Go 契约层输出不存在")
        if shared_ts_output is None:
            raise ValueError("[api-gen wails-transport] 共享 TypeScript 契约层输出不存在")

        matched_targets = self.list_targets(target_patterns)
        planned = tuple(
            self._build_plan(target, shared_go_output=shared_go_output, shared_ts_output=shared_ts_output)
            for target in matched_targets
        )
        for target in matched_targets:
            if self._count_selected_routes(entrypoints, target) == 0:
                raise ValueError(f"[api-gen wails-transport] target[{target.id}] include/exclude 过滤后没有可生成的 route")

            selection = self._selection_for_target(target)
            go_writer = WailsGoWriter(
                shared_go_output,
                version=target.version,
                overlay_name=target.overlay_name,
                module=golang_config.module,
                route_selection=selection,
                contract_graph=self.contract_graph,
            )
            go_writer.register(*entrypoints)
            go_writer.gen()

            if target.frontend_mode != "none":
                binding_manifest = self._build_wails_v3_binding_manifest(
                    entrypoints,
                    target=target,
                    go_writer=go_writer,
                    selection=selection,
                )
                ts_writer = TypeScriptWriter(
                    shared_ts_output,
                    template_lang="typescript",
                    transport_kind=f"wails-{target.version}",
                    transport_class_name=f"Wails{target.version.upper()}Transport",
                    allow_raw_ws=False,
                    overlay_name=target.overlay_name,
                    frontend_mode=target.frontend_mode,
                    include=target.include,
                    exclude=target.exclude,
                    wails_binding_manifest=binding_manifest,
                    contract_graph=self.contract_graph,
                )
                ts_writer.register(*entrypoints)
                ts_writer.gen()
        return planned
