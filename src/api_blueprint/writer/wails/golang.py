from __future__ import annotations

import logging
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import IO, TYPE_CHECKING, Generator, Optional, Set

from api_blueprint.engine.group import RouterGroup
from api_blueprint.engine.router import Router
from api_blueprint.engine.utils import join_path_imports
from api_blueprint.engine.envelope import NoEnvelope
from api_blueprint.writer.core.base import BaseBlueprint, BaseWriter
from api_blueprint.writer.core.contract_adapters import RouteContractIndex, RouteProtocolContract, route_protocol_from_router
from api_blueprint.writer.core.files import ensure_filepath_open
from api_blueprint.writer.core.templates import render
from api_blueprint.writer.golang.common import PackageName, internal_codegen_dir
from api_blueprint.writer.golang.naming import to_go_package_path
from api_blueprint.writer.golang.protos import GolangPackageLayout, GolangProto, GolangResponseEnvelope, ensure_model
from api_blueprint.writer.golang.route_view import GoRouteProtocolView
from api_blueprint.writer.golang.toolchain import GolangToolchain

from .selection import WailsRouteSelection


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("WailsGoWriter")
logger.setLevel(logging.INFO)

LANG = "wails"

if TYPE_CHECKING:
    from api_blueprint.contract import ContractGraph


class WailsRouter:
    def __init__(
        self,
        group: "WailsRouterGroup",
        router: Router,
        *,
        protocol: RouteProtocolContract | None = None,
    ):
        self.group = group
        self.router = router
        self.protocol = protocol or route_protocol_from_router(router)
        self.go = GoRouteProtocolView(router, protocol=self.protocol)
        self.contract = self.protocol.route
        self.json_envelope = GolangResponseEnvelope("RSP_JSON", self.protocol.response.envelope)

    @property
    def func_name(self) -> str:
        return self.go.func_name

    @property
    def ctx_type(self) -> str:
        return self.go.ctx_type

    @property
    def req_type(self) -> str:
        return self.go.req_type

    @property
    def rsp_type(self) -> str:
        return self.go.rsp_type

    @property
    def providers(self) -> str:
        return self.go.providers

    @property
    def provider_sequence(self) -> str:
        return self.go.providers

    @property
    def executor_field_name(self) -> str:
        return f"{self.contract.method_name}Executor"

    @property
    def query_alias_name(self) -> str | None:
        return self.go.query_alias_name

    @property
    def body_alias_name(self) -> str | None:
        if self.protocol.request.json.model is not None:
            return f"{self.req_type}_JSON"
        if self.protocol.request.form.model is not None:
            return f"{self.req_type}_FORM"
        return None

    @property
    def invoke_type(self) -> str:
        return f"INVOKE_{self.func_name}"

    @property
    def ws_connect_type(self) -> str:
        return f"WS_CONNECT_{self.func_name}"

    @property
    def ws_send_type(self) -> str:
        return f"WS_SEND_{self.func_name}"

    @property
    def ws_close_type(self) -> str:
        return f"WS_CLOSE_{self.func_name}"

    @property
    def connection_connect_type(self) -> str:
        return f"CONNECTION_CONNECT_{self.func_name}"

    @property
    def channel_send_type(self) -> str:
        return f"CHANNEL_SEND_{self.func_name}"

    @property
    def connection_close_type(self) -> str:
        return f"CONNECTION_CLOSE_{self.func_name}"

    @property
    def ws_payload_alias_name(self) -> str | None:
        if len(self.protocol.recvs) != 1:
            return None
        return f"{self.ws_send_type}_BODY"

    @property
    def ws_payload_target(self) -> str:
        if len(self.protocol.recvs) != 1:
            return "any"
        return self.group.bp.shared_common_proto_ref(self.protocol.recvs[0])

    @property
    def server_message_type(self) -> str:
        return self.go.server_message_type

    @property
    def client_message_type(self) -> str:
        return self.go.client_message_type

    @property
    def close_message_type(self) -> str:
        return self.go.close_message_type

    @property
    def connection_scope(self) -> str:
        return self.contract.connection_scope.value if self.contract.connection_scope else ""

    @property
    def connection_delivery(self) -> str:
        return self.contract.connection_delivery.value if self.contract.connection_delivery else ""

    @property
    def ordered_connection_delivery(self) -> bool:
        return self.connection_delivery == "ordered"

    @property
    def service_name(self) -> str:
        return self.contract.service_name

    @property
    def namespace(self) -> str:
        return self.contract.namespace

    @property
    def connect_func(self) -> str:
        return self.contract.ws.connect_method if self.contract.ws is not None else ""

    @property
    def send_func(self) -> str:
        return self.contract.ws.send_method if self.contract.ws is not None else ""

    @property
    def close_func(self) -> str:
        return self.contract.ws.close_method if self.contract.ws is not None else ""

    @property
    def connection_connect_func(self) -> str:
        if self.contract.stream is not None:
            return self.contract.stream.connect_method
        if self.contract.channel is not None:
            return self.contract.channel.connect_method
        return ""

    @property
    def channel_send_func(self) -> str:
        return self.contract.channel.send_method if self.contract.channel is not None else ""

    @property
    def connection_close_func(self) -> str:
        if self.contract.stream is not None:
            return self.contract.stream.close_method
        if self.contract.channel is not None:
            return self.contract.channel.close_method
        return ""

    @property
    def route_id(self) -> str:
        return self.contract.route_id

    @property
    def event_base(self) -> str:
        if self.contract.stream is not None:
            return self.contract.stream.event_base
        if self.contract.channel is not None:
            return self.contract.channel.event_base
        if self.contract.ws is not None:
            return self.contract.ws.event_base
        return ""

    @property
    def root(self) -> str:
        return self.router.group.bp.root.strip("/") or "root"

    @property
    def group_name(self) -> str:
        return self.router.group.branch.strip("/")

    @property
    def methods(self) -> list[str]:
        return self.go.methods

    @property
    def url(self) -> str:
        return self.contract.url

    @property
    def has_ws(self) -> bool:
        return self.contract.ws is not None

    @property
    def is_stream(self) -> bool:
        return self.contract.stream is not None

    @property
    def is_channel(self) -> bool:
        return self.contract.channel is not None

    @property
    def is_connection(self) -> bool:
        return self.is_stream or self.is_channel

    @property
    def local_query_type_expr(self) -> str:
        return self.query_alias_name or "any"

    @property
    def local_body_type_expr(self) -> str:
        return self.body_alias_name or "any"

    @property
    def local_ws_payload_type_expr(self) -> str:
        return self.ws_payload_alias_name or "any"

    @property
    def bind_query(self) -> bool:
        return self.go.bind_query

    @property
    def bind_json(self) -> bool:
        return self.protocol.request.json.model is not None

    @property
    def bind_form(self) -> bool:
        return self.protocol.request.form.model is not None

    @property
    def executor_body_type_expr(self) -> str:
        if self.has_ws or self.is_connection:
            return "any"
        return self.local_body_type_expr

    @property
    def executor_type_expr(self) -> str:
        return (
            f"*sharedprovider.RouteExecutor["
            f"{self.local_query_type_expr}, "
            f"{self.executor_body_type_expr}, "
            f"{self.rsp_type}"
            f"]"
        )

    @property
    def is_json_response(self) -> bool:
        return self.protocol.response.media_type == "application/json"

    @property
    def is_xml_response(self) -> bool:
        return self.protocol.response.media_type == "application/xml"

    @property
    def is_text_response(self) -> bool:
        return not self.is_json_response

    @property
    def uses_fmt_text_response(self) -> bool:
        return self.is_text_response and not self.is_xml_response

    @property
    def response_envelope_name(self) -> str:
        return self.protocol.response.envelope.__name__

    @property
    def has_wrapped_json_response(self) -> bool:
        return self.is_json_response and self.protocol.response.envelope is not NoEnvelope

    @property
    def service_response_type_expr(self) -> str:
        if self.has_wrapped_json_response:
            return self.json_envelope.type_reference(self.rsp_type, package="sharedprovider")
        if self.is_json_response:
            return f"*{self.rsp_type}"
        return "string"

    @property
    def shared_json_wrap_call(self) -> str:
        return f"sharedprovider.WrapRSP_JSON_{self.response_envelope_name}(response, invokeErr)"


class WailsRouterGroup:
    def __init__(self, bp: "WailsBlueprint", group: RouterGroup, routers: list[Router]):
        self.bp = bp
        self.group = group
        self._routers = routers

    @property
    def routers(self) -> list[Router]:
        return self._routers

    @property
    def package(self) -> str:
        branch = self.group.branch.strip("/")
        if branch:
            return to_go_package_path(branch, fallback="root")
        return self.bp.root_package

    @property
    def branch(self) -> str:
        return self.group.branch.strip("/")

    @property
    def shared_imports(self) -> str:
        if not self.branch:
            return self.bp.shared_root_imports
        return join_path_imports(self.bp.shared_root_imports, self.package)

    @property
    def overlay_imports(self) -> str:
        imports = join_path_imports(
            self.bp.writer.shared_views_imports,
            "transports",
            self.bp.writer.overlay_dir_name,
            self.bp.package,
        )
        if self.branch:
            imports = join_path_imports(imports, self.package)
        return imports

    @property
    def binding_package(self) -> str:
        views = list(self.views())
        if not views:
            return self.package
        return views[0].namespace

    @property
    def service_name(self) -> str:
        views = list(self.views())
        if not views:
            return "Service"
        return views[0].service_name

    def views(self) -> Generator[WailsRouter, None, None]:
        for router in self.routers:
            yield WailsRouter(self, router, protocol=self.bp.protocol_for_router(router))


class WailsBlueprint(BaseBlueprint["WailsGoWriter"]):
    def __init__(self, writer: "WailsGoWriter", bp):
        super().__init__(writer, bp)
        self.router_groups: Optional[list[WailsRouterGroup]] = None

    @property
    def package(self) -> str:
        return self.root_package

    @property
    def root_package(self) -> str:
        return to_go_package_path(self.bp.root.strip("/"), fallback="root")

    @property
    def shared_root_imports(self) -> str:
        return join_path_imports(self.writer.shared_routes_imports, self.package)

    @property
    def shared_types_imports(self) -> str:
        return join_path_imports(self.shared_root_imports, internal_codegen_dir(PackageName.COM_PROTOS))

    def shared_common_proto_ref(self, model: object) -> str:
        proto = GolangProto.from_model(ensure_model(model))
        return f"sharedtypes.{proto.name}"

    def protocol_for_router(self, router: Router) -> RouteProtocolContract:
        return self.writer.route_protocol_for(router)

    def get_router_groups(self) -> list[WailsRouterGroup]:
        if self.router_groups is None:
            selected_by_group: dict[RouterGroup, list[Router]] = {}
            ordered_groups: list[RouterGroup] = []
            groups: list[WailsRouterGroup] = []
            selection = self.writer.route_selection
            for group, router in self.iter_router():
                if selection is not None:
                    route_name = self.protocol_for_router(router).route.func_name
                    if not selection.includes_route(router, route_name=route_name):
                        continue
                if group not in selected_by_group:
                    selected_by_group[group] = []
                    ordered_groups.append(group)
                selected_by_group[group].append(router)
            for group in ordered_groups:
                groups.append(WailsRouterGroup(self, group, selected_by_group[group]))
            self.router_groups = groups
        return self.router_groups

    def gen(self) -> None:
        ctx = {"writer": self.writer, "bp": self}
        with self.writer.write_file(self.writer.runtime_dir / "gen_runtime.go", overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "gen_runtime.go", ctx, "runtime"))

        for group in self.get_router_groups():
            self.gen_group(group)

    def gen_group(self, group: WailsRouterGroup) -> None:
        group_dir = self.writer.views_dir / "transports" / self.writer.overlay_dir_name / self.package
        if group.branch:
            group_dir /= group.package
        ctx = {"writer": self.writer, "bp": self, "router_group": group}
        for template_name in ("gen_overlay.go", "gen_service.go", "impl_service.go"):
            with self.writer.write_file(group_dir / template_name, overwrite=template_name.startswith("gen_")) as handle:
                if handle:
                    handle.write(render(LANG, template_name, ctx, "go/route"))


class WailsGoWriter(BaseWriter[WailsBlueprint]):
    def __init__(
        self,
        working_dir: str | Path = ".",
        *,
        version: str,
        overlay_name: str,
        module: str | None = None,
        runtime_package: str = "wailstransport",
        route_selection: WailsRouteSelection | None = None,
        contract_graph: ContractGraph | None = None,
    ):
        super().__init__(working_dir)
        self.version = version
        self.overlay_name = overlay_name
        self.runtime_package = runtime_package
        self.route_selection = route_selection
        self.route_contract_index = RouteContractIndex.from_graph(contract_graph) if contract_graph is not None else None
        self.toolchain = GolangToolchain(logger)
        self._written_files: Set[str] = set()

        shared_go_module = self.toolchain.resolve_module_import(working_dir, module=module, label="[wails]")
        logger.info("[*] shared go gomodule: %s", shared_go_module.module)
        self.module_import = shared_go_module.import_path
        self.shared_packages = GolangPackageLayout(
            module_import=shared_go_module.import_path,
            views_package="",
            errors_package="runtime/errors",
        )

    @property
    def overlay_dir_name(self) -> str:
        return self.overlay_name

    @property
    def runtime_imports(self) -> str:
        return join_path_imports(
            self.module_import,
            self.shared_packages.views_package,
            "transports",
            self.overlay_dir_name,
        )

    @property
    def shared_views_imports(self) -> str:
        return self.shared_packages.views_imports

    @property
    def shared_routes_imports(self) -> str:
        return self.shared_packages.routes_imports

    @property
    def shared_provider_imports(self) -> str:
        return self.shared_packages.provider_imports

    @property
    def views_dir(self) -> Path:
        return self.working_dir / self.shared_packages.views_package

    @property
    def runtime_dir(self) -> Path:
        return self.views_dir / "transports" / self.overlay_dir_name

    def validate_package_contract(self) -> None:
        return None

    def _ensure_route_contract_index(self) -> RouteContractIndex:
        if self.route_contract_index is None:
            from api_blueprint.contract import build_contract_graph

            self.route_contract_index = RouteContractIndex.from_graph(build_contract_graph([bp.bp for bp in self.bps]))
        return self.route_contract_index

    def route_protocol_for(self, router: Router) -> RouteProtocolContract:
        return self._ensure_route_contract_index().protocol_for_router(router)

    def gen(self) -> None:
        self.validate_package_contract()
        self.cleanup_legacy_overlay_files()
        for bp in self.bps:
            bp.build()
            bp.gen()

        if self._written_files:
            for file in self._written_files:
                self.toolchain.run_format(file)

    def cleanup_legacy_overlay_files(self) -> None:
        legacy_runtime = self.views_dir / f"_{self.overlay_name}"
        if legacy_runtime.exists():
            shutil.rmtree(legacy_runtime)
        if not self.views_dir.exists():
            return
        for overlay_dir in sorted(self.views_dir.rglob(f"_{self.overlay_name}"), key=lambda path: len(path.parts), reverse=True):
            if overlay_dir.is_dir():
                shutil.rmtree(overlay_dir)
        transport_dir = self.views_dir / "transports" / self.overlay_dir_name
        legacy_runtime_dir = transport_dir / "runtime"
        if legacy_runtime_dir.exists():
            shutil.rmtree(legacy_runtime_dir)
        if transport_dir.exists():
            for binding_dir in sorted(transport_dir.rglob("bindings"), key=lambda path: len(path.parts), reverse=True):
                if self._is_legacy_binding_dir(binding_dir):
                    shutil.rmtree(binding_dir)

    @staticmethod
    def _is_legacy_binding_dir(path: Path) -> bool:
        if not path.is_dir():
            return False
        generated = path / "gen_service.go"
        if not generated.is_file():
            return False
        try:
            text = generated.read_text(encoding="utf-8")
        except OSError:
            return False
        return "generated.New" in text

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
            path = Path(filepath_str)
            if path.is_file():
                self._written_files.add(str(path.parent))
        else:
            logger.info("[.] Skipped: %s", filepath_str)
