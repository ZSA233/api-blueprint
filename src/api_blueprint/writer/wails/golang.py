from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Generator, Optional, Set

from api_blueprint.engine.group import RouterGroup
from api_blueprint.engine.router import Router
from api_blueprint.engine.utils import join_path_imports
from api_blueprint.engine.wrapper import NoneWrapper
from api_blueprint.writer.core.base import BaseBlueprint, BaseWriter
from api_blueprint.writer.core.contracts import route_contract
from api_blueprint.writer.core.files import ensure_filepath_open
from api_blueprint.writer.core.templates import render
from api_blueprint.writer.golang.blueprint import GolangRouter
from api_blueprint.writer.golang.common import PackageName, internal_codegen_dir
from api_blueprint.writer.golang.protos import GolangPackageLayout, GolangProto, GolangResponseWrapper, ensure_model
from api_blueprint.writer.golang.toolchain import GolangToolchain

from .selection import WailsRouteSelection


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("WailsGoWriter")
logger.setLevel(logging.INFO)

LANG = "wails"


class WailsRouter:
    def __init__(self, group: "WailsRouterGroup", router: Router):
        self.group = group
        self.router = router
        self.go = GolangRouter(router)
        self.contract = route_contract(router)
        self.json_wrapper = GolangResponseWrapper("RSP_JSON", router.response_wrapper)

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
    def executor_field_name(self) -> str:
        return f"{self.contract.method_name}Executor"

    @property
    def query_alias_name(self) -> str | None:
        if self.router.req_query is None:
            return None
        return f"{self.req_type}_QUERY"

    @property
    def body_alias_name(self) -> str | None:
        if self.router.req_json is not None:
            return f"{self.req_type}_JSON"
        if self.router.req_form is not None:
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
    def ws_payload_alias_name(self) -> str | None:
        if len(self.router.recvs) != 1:
            return None
        return f"{self.ws_send_type}_BODY"

    @property
    def ws_payload_target(self) -> str:
        if len(self.router.recvs) != 1:
            return "any"
        return self.group.bp.shared_common_proto_ref(self.router.recvs[0])

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
    def route_id(self) -> str:
        return self.contract.route_id

    @property
    def has_ws(self) -> bool:
        return self.contract.ws is not None

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
        return self.router.req_query is not None

    @property
    def bind_json(self) -> bool:
        return self.router.req_json is not None

    @property
    def bind_form(self) -> bool:
        return self.router.req_form is not None

    @property
    def executor_body_type_expr(self) -> str:
        if self.has_ws:
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
        return self.router.rsp_media_type == "application/json"

    @property
    def is_xml_response(self) -> bool:
        return self.router.rsp_media_type == "application/xml"

    @property
    def is_text_response(self) -> bool:
        return not self.is_json_response

    @property
    def uses_fmt_text_response(self) -> bool:
        return self.is_text_response and not self.is_xml_response

    @property
    def response_wrapper_name(self) -> str:
        return self.router.response_wrapper.__name__

    @property
    def has_wrapped_json_response(self) -> bool:
        return self.is_json_response and self.router.response_wrapper is not NoneWrapper

    @property
    def service_response_type_expr(self) -> str:
        if self.has_wrapped_json_response:
            return self.json_wrapper.type_reference(self.rsp_type, package="sharedprovider")
        if self.is_json_response:
            return f"*{self.rsp_type}"
        return "string"

    @property
    def shared_json_wrap_call(self) -> str:
        return f"sharedprovider.WrapRSP_JSON_{self.response_wrapper_name}[{self.rsp_type}](response, invokeErr)"


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
            return branch
        return self.group.bp.root.strip("/")

    @property
    def branch(self) -> str:
        return self.group.branch.strip("/")

    @property
    def shared_imports(self) -> str:
        if not self.branch:
            return self.bp.shared_root_imports
        return join_path_imports(self.bp.shared_root_imports, self.package)

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
            yield WailsRouter(self, router)


class WailsBlueprint(BaseBlueprint["WailsGoWriter"]):
    def __init__(self, writer: "WailsGoWriter", bp):
        super().__init__(writer, bp)
        self.router_groups: Optional[list[WailsRouterGroup]] = None

    @property
    def package(self) -> str:
        return self.bp.root.strip("/")

    @property
    def shared_root_imports(self) -> str:
        return join_path_imports(self.writer.shared_views_imports, self.package)

    @property
    def shared_protos_imports(self) -> str:
        return join_path_imports(self.shared_root_imports, internal_codegen_dir(PackageName.COM_PROTOS))

    def shared_common_proto_ref(self, model: object) -> str:
        proto = GolangProto.from_model(ensure_model(model))
        return f"sharedprotos.{proto.name}"

    def get_router_groups(self) -> list[WailsRouterGroup]:
        if self.router_groups is None:
            selected_by_group: dict[RouterGroup, list[Router]] = {}
            ordered_groups: list[RouterGroup] = []
            groups: list[WailsRouterGroup] = []
            selection = self.writer.route_selection
            for group, router in self.iter_router():
                if selection is not None and not selection.includes_route(router):
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
        runtime_dir = self.writer.runtime_dir
        with self.writer.write_file(runtime_dir / "gen_runtime.go", overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "gen_runtime.go", ctx, "runtime"))

        for group in self.get_router_groups():
            self.gen_group(group)

    def gen_group(self, group: WailsRouterGroup) -> None:
        group_dir = self.writer.views_dir / self.package
        if group.branch:
            group_dir /= group.package
        group_dir /= self.writer.overlay_dir_name
        ctx = {"writer": self.writer, "bp": self, "router_group": group}
        for template_name in ("gen_overlay.go", "gen_service.go"):
            with self.writer.write_file(group_dir / template_name, overwrite=True) as handle:
                if handle:
                    handle.write(render(LANG, template_name, ctx, "go/route"))

        binding_dir = group_dir / "bindings"
        with self.writer.write_file(binding_dir / "gen_service.go", overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "gen_service.go", ctx, "go/bindings"))
        with self.writer.write_file(binding_dir / "impl_service.go", overwrite=False) as handle:
            if handle:
                handle.write(render(LANG, "impl_service.go", ctx, "go/bindings"))


class WailsGoWriter(BaseWriter[WailsBlueprint]):
    def __init__(
        self,
        working_dir: str | Path = ".",
        *,
        version: str,
        overlay_name: str,
        module: str | None = None,
        provider_package: str = PackageName.PROVIDER.value,
        runtime_package: str = "runtime",
        route_selection: WailsRouteSelection | None = None,
    ):
        super().__init__(working_dir)
        self.version = version
        self.overlay_name = overlay_name
        self.provider_package = provider_package
        self.runtime_package = runtime_package
        self.route_selection = route_selection
        self.toolchain = GolangToolchain(logger)
        self._written_files: Set[str] = set()

        shared_go_module = self.toolchain.resolve_module_import(working_dir, module=module, label="[wails]")
        logger.info("[*] shared go gomodule: %s", shared_go_module.module)
        self.module_import = shared_go_module.import_path
        self.shared_packages = GolangPackageLayout(
            module_import=shared_go_module.import_path,
            views_package=PackageName.VIEWS.value,
            provider_package=provider_package,
            errors_package=PackageName.ERROR.value,
        )

    @property
    def overlay_dir_name(self) -> str:
        return f"_{self.overlay_name}"

    @property
    def runtime_imports(self) -> str:
        return join_path_imports(
            self.module_import,
            self.shared_packages.views_package,
            self.overlay_dir_name,
            self.runtime_package,
        )

    @property
    def shared_views_imports(self) -> str:
        return self.shared_packages.views_imports

    @property
    def shared_provider_imports(self) -> str:
        return self.shared_packages.provider_imports

    @property
    def views_dir(self) -> Path:
        return self.working_dir / self.shared_packages.views_package

    @property
    def runtime_dir(self) -> Path:
        return self.views_dir / self.overlay_dir_name / self.runtime_package

    def validate_package_contract(self) -> None:
        for bp in self.bps:
            root_name = bp.root_name
            if root_name and root_name == self.provider_package:
                raise ValueError(
                    f"[gen_wails] provider_package[{self.provider_package}] "
                    f"与 blueprint root[{root_name}] 冲突；请调整 [golang].provider_package 或 blueprint root"
                )

    def gen(self) -> None:
        self.validate_package_contract()
        for bp in self.bps:
            bp.build()
            bp.gen()

        if self._written_files:
            for file in self._written_files:
                self.toolchain.run_format(file)

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
