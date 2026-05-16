from __future__ import annotations

import enum
import shutil
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator, Optional, Set, Type

from api_blueprint.engine.group import RouterGroup
from api_blueprint.engine.model import Error, iter_enum_classes
from api_blueprint.engine.router import Router
from api_blueprint.engine.utils import join_path_imports
from api_blueprint.writer.core.base import BaseBlueprint
from api_blueprint.writer.core.contract_adapters import RouteProtocolContract
from api_blueprint.writer.core.contracts import RouteContract
from api_blueprint.writer.core.templates import iter_render, render

from api_blueprint.writer.golang.naming import to_go_exported_name, to_go_package_path
from api_blueprint.writer.golang.route_view import GoRouteProtocolView

from .binary_schema import compact_go_binary_source, go_binary_state_fields, unique_go_binary_schemas
from .planner import build_go_server_blueprint_plan, build_go_server_route_group_plan
from ..common import LANG, PackageName, internal_codegen_dir
from ..protos import (
    GolangEnum,
    GolangProto,
)

if TYPE_CHECKING:
    from .writer import GolangWriter


class GolangError:
    def __init__(self, error: Error):
        self._err = error

    @property
    def code(self) -> int:
        return self._err.code

    @property
    def message(self) -> str:
        return self._err.message

    @property
    def id(self) -> str:
        cls_name, key = self._err.__key__
        return f"{cls_name}.{key}"

    @property
    def key(self) -> str:
        _cls_name, key = self._err.__key__
        return key.upper()

    @property
    def toast_key(self) -> str:
        toast = getattr(self._err, "toast", None)
        return str(getattr(toast, "key", "") or self.id)

    @property
    def toast_default(self) -> str:
        toast = getattr(self._err, "toast", None)
        return str(getattr(toast, "default", "") or self.message)

    @property
    def toast_level(self) -> str:
        toast = getattr(self._err, "toast", None)
        return str(getattr(toast, "level", "") or "error")


class GolangErrorGroup:
    def __init__(self, package: str, imports: str, gen_dir: str, errs: list[Error]):
        self.package = package
        self.imports = imports
        self.gen_dir = gen_dir
        self.errors = [GolangError(err) for err in errs]

    def error_vars(self) -> Generator[GolangError, None, None]:
        yield from self.errors


class GolangRouterGroup:
    def __init__(self, bp: "GolangBlueprint", group: RouterGroup):
        self.bp = bp
        self.group = group
        self._routers: Optional[list[Router]] = None

    @property
    def routers(self):
        if self._routers is None:
            self._routers = list(self.group)
        return self._routers

    @property
    def package(self) -> str:
        if self.branch:
            return to_go_package_path(self.branch, fallback="root")
        return self.bp.root_package

    @property
    def package_leaf(self) -> str:
        return self.package.rsplit("/", 1)[-1]

    @property
    def export_name(self) -> str:
        return to_go_exported_name(self.package_leaf, fallback="Z")

    @property
    def shared_alias(self) -> str:
        return f"shared{self.export_name}"

    @property
    def http_package(self) -> str:
        return self.package_leaf

    @property
    def root(self) -> str:
        return self.group.bp.root.strip("/")

    @property
    def branch(self) -> str:
        return self.group.branch.strip("/")

    @property
    def imports(self) -> str:
        return self.bp.imports if not self.branch else join_path_imports(self.bp.imports, self.package)

    @property
    def http_imports(self) -> str:
        imports = join_path_imports(self.bp.writer.http_adapter_imports, self.bp.root_package)
        if self.branch:
            imports = join_path_imports(imports, self.package)
        return imports

    @property
    def binary_package(self) -> str:
        return "binary"

    @property
    def binary_gen_path(self) -> str:
        return "_gen_binary"

    @property
    def binary_imports(self) -> str:
        return join_path_imports(self.imports, self.binary_gen_path)

    def formatters(self, update: Optional[dict[str, str]] = None) -> dict[str, str]:
        formatters = self.bp.formatters()
        formatters.update(
            {
                "binary_package": self.binary_package,
                "binary_imports": self.binary_imports,
            }
        )
        formatters.update({key + "$": value + "." for key, value in formatters.items() if key.endswith("_package")})
        if update:
            formatters.update(update)
        return formatters

    def __len__(self) -> int:
        return len(self.group)

    def _router_view(self, router: Router) -> GoRouteProtocolView:
        return GoRouteProtocolView(router, protocol=self.bp.protocol_for_router(router))

    def interfaces(self) -> Generator[dict[str, Any], None, None]:
        for router in self.group:
            view = self._router_view(router)
            yield {
                "func": view.func_name,
                "ctx_type": view.ctx_type,
                "req_type": view.req_type,
                "rsp_type": view.rsp_type,
                "signature": view.interface_signature,
                "default_body": view.default_body,
                "is_connection": view.is_connection,
            }

    def registers(self) -> Generator[dict[str, Any], None, None]:
        for router in self.group:
            view = self._router_view(router)
            for method in view.methods:
                yield {
                    "func": view.func_name,
                    "method": method,
                    "api": view.url,
                    "provider": view.providers,
                    "root": view.root,
                    "group": view.group,
                    "namespace": view.namespace,
                    "service": view.service_name,
                    "operation": view.func_name,
                    "route_id": view.route_id,
                    "methods": view.methods,
                    "query_type": view.local_query_type_expr,
                    "body_type": view.executor_body_type_expr,
                    "rsp_type": view.rsp_type,
                    "server_message_type": view.server_message_type,
                    "client_message_type": view.client_message_type,
                    "close_message_type": view.close_message_type,
                    "http_query_type": view.shared_type_expr(view.local_query_type_expr),
                    "http_body_type": view.shared_type_expr(view.executor_body_type_expr),
                    "http_rsp_type": view.shared_type_expr(view.rsp_type),
                    "http_server_message_type": view.shared_type_expr(view.server_message_type),
                    "http_client_message_type": view.shared_type_expr(view.client_message_type),
                    "http_close_message_type": view.shared_type_expr(view.close_message_type),
                    "connection_scope": view.contract.connection_scope.value if view.contract.connection_scope else "",
                    "is_stream": view.is_stream,
                    "is_channel": view.is_channel,
                    "is_connection": view.is_connection,
                    "raw_response": view.http_raw_response,
                    "bind_query": view.bind_query,
                    "bind_json": view.bind_json,
                    "bind_form": view.bind_form,
                    "bind_binary": view.bind_binary,
                }

    def protos(self) -> Generator[GolangProto, None, None]:
        for router in self.group:
            yield from self._router_view(router).protos()

    def com_protos(self) -> Generator[GolangProto, None, None]:
        for router in self.group:
            yield from self._router_view(router).com_protos()

    def binary_schemas(self) -> list[Any]:
        schemas = [router.req_binary_schema for router in self.group if router.req_binary_schema is not None]
        return unique_go_binary_schemas(schemas)

    def implements(self) -> Generator[dict[str, Any], None, None]:
        for router in self.group:
            view = self._router_view(router)
            yield {
                "func": view.func_name,
                "ctx_type": view.ctx_type,
                "req_type": view.req_type,
                "rsp_type": view.rsp_type,
                "signature": view.interface_signature,
                "default_body": view.default_body,
                "is_connection": view.is_connection,
            }

    def message_unions(self) -> Generator[dict[str, Any], None, None]:
        for router in self.group:
            yield from self._router_view(router).message_unions()

    @property
    def uses_connection_runtime(self) -> bool:
        return any(self._router_view(router).is_connection for router in self.group)


class GolangBlueprint(BaseBlueprint["GolangWriter"]):
    router_groups: Optional[list[GolangRouterGroup]] = None

    def contract_for_router(self, router: Router) -> RouteContract:
        return self.writer.route_contract_for(router)

    def protocol_for_router(self, router: Router) -> RouteProtocolContract:
        return self.writer.route_protocol_for(router)

    def get_router_groups(self) -> list[GolangRouterGroup]:
        if self.router_groups is None:
            group_set: Set[RouterGroup] = set()
            groups = []
            for group, _router in self.iter_router():
                if group in group_set:
                    continue
                group_set.add(group)
                groups.append(GolangRouterGroup(self, group))
            self.router_groups = groups
        return self.router_groups

    @property
    def root_router_group(self) -> GolangRouterGroup | None:
        for group in self.get_router_groups():
            if not group.branch:
                return group
        return None

    @property
    def package(self) -> str:
        return self.root_package

    @property
    def root_package(self) -> str:
        return to_go_package_path(self.bp.root.strip("/"), fallback="root")

    @property
    def package_leaf(self) -> str:
        return self.package.rsplit("/", 1)[-1]

    @property
    def http_package(self) -> str:
        return self.package_leaf

    @property
    def imports(self) -> str:
        return join_path_imports(self.writer.routes_imports, self.package)

    @property
    def com_proto_package(self) -> str:
        return PackageName.COM_PROTOS.value

    @property
    def com_proto_gen_path(self) -> str:
        return internal_codegen_dir(PackageName.COM_PROTOS)

    @property
    def com_proto_imports(self) -> str:
        return join_path_imports(self.imports, self.com_proto_gen_path)

    @property
    def com_enum_package(self) -> str:
        return PackageName.COM_ENUMS.value

    @property
    def com_enum_gen_path(self) -> str:
        return internal_codegen_dir(PackageName.COM_ENUMS)

    @property
    def com_enum_imports(self) -> str:
        return join_path_imports(self.imports, self.com_enum_gen_path)

    @property
    def binary_package(self) -> str:
        return "binary"

    @property
    def binary_gen_path(self) -> str:
        return "_gen_binary"

    @property
    def binary_imports(self) -> str:
        return join_path_imports(self.imports, self.binary_gen_path)

    @property
    def binary_runtime_package(self) -> str:
        return "binaryruntime"

    @property
    def binary_runtime_gen_path(self) -> str:
        return "runtime/binary"

    @property
    def binary_runtime_imports(self) -> str:
        return join_path_imports(self.writer.views_imports, self.binary_runtime_gen_path)

    def formatters(self, update: Optional[dict[str, str]] = None) -> dict[str, str]:
        formatters = self.writer.formatters()
        formatters.update(
            {
                "enums_package": self.com_enum_package,
                "enums_imports": self.com_enum_imports,
                "protos_package": self.com_proto_package,
                "protos_imports": self.com_proto_imports,
                "binary_package": self.binary_package,
                "binary_imports": self.binary_imports,
                "binary_runtime_package": self.binary_runtime_package,
                "binary_runtime_imports": self.binary_runtime_imports,
            }
        )
        formatters.update({key + "$": value + "." for key, value in formatters.items() if key.endswith("_package")})
        if update:
            formatters.update(update)
        return formatters

    def protos(self) -> Generator[GolangProto, None, None]:
        seen = set()
        for group in self.get_router_groups():
            for proto in group.protos():
                if proto.name in seen:
                    continue
                seen.add(proto.name)
                yield proto

    def com_protos(self) -> Generator[GolangProto, None, None]:
        seen = set()
        for group in self.get_router_groups():
            for proto in group.com_protos():
                if proto.name in seen:
                    continue
                seen.add(proto.name)
                yield proto

    def com_enums(self) -> Generator[GolangEnum, None, None]:
        seen: Set[Type[enum.Enum]] = set()
        for proto in chain(self.protos(), self.com_protos()):
            for enum_cls in iter_enum_classes(proto.model_type):
                if enum_cls in seen:
                    continue
                golang_enum = GolangEnum.from_enum(enum_cls)
                if golang_enum is None:
                    continue
                seen.add(enum_cls)
                yield golang_enum

    def gen_views(self) -> None:
        self.validate_reserved_paths()
        plan = build_go_server_blueprint_plan(self.writer, self)
        view_dir = plan.route_root_dir
        ctx = {"writer": self.writer, "bp": self}

        self.cleanup_legacy_http_files()
        self.cleanup_binary_codegen_dirs(view_dir)

        with self.writer.write_file(view_dir / self.com_proto_gen_path / "protos.go", overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "protos.go", ctx, "server/views/_gen_protos"))

        enums_path = view_dir / self.com_enum_gen_path / "enums.go"
        with self.writer.write_file(enums_path, overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "enums.go", ctx, "server/views/_gen_enums"))
        self.writer.toolchain.run_go_enum(enums_path)

        if self.binary_schemas():
            runtime_ctx = {
                **ctx,
                "binary_runtime_package": self.binary_runtime_package,
            }
            with self.writer.write_file(
                plan.binary_runtime_dir / "gen_runtime.go",
                overwrite=True,
            ) as handle:
                if handle:
                    handle.write(
                        compact_go_binary_source(
                            render(
                                LANG,
                                "gen_runtime.go",
                                runtime_ctx,
                                "server/views/runtime/binary",
                            )
                        )
                    )

        with self.writer.write_file(view_dir / "gen_blueprint.go", overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "gen_blueprint.go", ctx, "server/views"))

        for group in self.get_router_groups():
            self.gen_routers(group)

        if self.writer.http_adapter_enabled:
            self.gen_http_adapter()

    def cleanup_legacy_http_files(self) -> None:
        legacy_engine = self.writer.working_dir / self.writer.views_package / "engine.go"
        if legacy_engine.exists():
            legacy_engine.unlink()
        views_dir = self.writer.working_dir / self.writer.views_package
        if not views_dir.exists():
            return
        for http_dir in sorted(views_dir.rglob("_http"), key=lambda path: len(path.parts), reverse=True):
            if http_dir.is_dir():
                shutil.rmtree(http_dir)
        legacy_http_runtime = views_dir / "transports" / "http" / "runtime"
        if legacy_http_runtime.exists():
            shutil.rmtree(legacy_http_runtime)
        if self.writer.http_adapter_enabled:
            return
        transports_http = views_dir / "transports" / "http"
        if transports_http.exists():
            shutil.rmtree(transports_http)

    def cleanup_binary_codegen_dirs(self, view_dir: Path) -> None:
        for binary_dir in sorted(view_dir.rglob(self.binary_gen_path), key=lambda path: len(path.parts), reverse=True):
            if binary_dir.is_dir():
                shutil.rmtree(binary_dir)
        legacy_runtime_dir = view_dir / "_gen_binary_runtime"
        if legacy_runtime_dir.exists():
            shutil.rmtree(legacy_runtime_dir)

    def gen_http_adapter(self) -> None:
        ctx = {"writer": self.writer, "bp": self}
        plan = build_go_server_blueprint_plan(self.writer, self)
        with self.writer.write_file(self.writer.http_transport_dir / "gen_engine.go", overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "gen_engine.go", ctx, "server/views/transports/http"))

        with self.writer.write_file(plan.http_root_dir / "gen_blueprint.go", overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "gen_blueprint.go", ctx, "server/views/transports/http"))

        for group in self.get_router_groups():
            self.gen_http_router(group)

    def validate_reserved_paths(self) -> None:
        self._validate_reserved_segments(self.bp.root, label="blueprint root")
        for group in self.get_router_groups():
            if group.branch:
                self._validate_reserved_segments(group.branch, label="router group")

    def _validate_reserved_segments(self, raw_path: str, *, label: str) -> None:
        segments = [segment for segment in raw_path.strip("/").split("/") if segment]
        for segment in segments:
            if segment.startswith("_"):
                raise ValueError(
                    f"[go-server] {label}[{raw_path}] 使用了生成器保留目录段[{segment}]；"
                    "以下划线开头的 Go 目录由 api-blueprint 保留"
                )

    def gen_routers(self, group: GolangRouterGroup) -> None:
        plan = build_go_server_route_group_plan(self.writer, self, group)
        ctx = {"writer": self.writer, "bp": self, "router_group": group}
        self.gen_binary_router(group, plan.route_dir)
        for name, text in iter_render(LANG, ctx, "server/views/route"):
            overwrite = name.startswith("gen_")
            with self.writer.write_file(plan.route_dir / name, overwrite=overwrite) as handle:
                if handle:
                    handle.write(text)

    def gen_binary_router(self, group: GolangRouterGroup, view_dir: Path) -> None:
        binary_schemas = group.binary_schemas()
        if not binary_schemas:
            return
        binary_ctx = {
            "writer": self.writer,
            "bp": self,
            "router_group": group,
            "binary_package": group.binary_package,
            "binary_runtime_imports": self.binary_runtime_imports,
            "binary_schemas": binary_schemas,
            "binary_state_fields": go_binary_state_fields(binary_schemas),
            "binary_needs_math": any(schema.needs_math for schema in binary_schemas),
            "binary_needs_unsafe": any(schema.needs_unsafe for schema in binary_schemas),
        }
        with self.writer.write_file(view_dir / group.binary_gen_path / "gen_binary.go", overwrite=True) as handle:
            if handle:
                handle.write(
                    compact_go_binary_source(
                        render(
                            LANG,
                            "gen_binary.go",
                            binary_ctx,
                            "server/views/_gen_binary",
                        )
                    )
                )

    def gen_http_router(self, group: GolangRouterGroup) -> None:
        plan = build_go_server_route_group_plan(self.writer, self, group)
        ctx = {"writer": self.writer, "bp": self, "router_group": group}
        for name, text in iter_render(LANG, ctx, "server/views/route/transports/http"):
            overwrite = name.startswith("gen_")
            with self.writer.write_file(plan.http_dir / name, overwrite=overwrite) as handle:
                if handle:
                    handle.write(text)

    def binary_schemas(self):
        schemas = []
        for _group, router in self.iter_router():
            if router.req_binary_schema is not None:
                schemas.append(router.req_binary_schema)
        return unique_go_binary_schemas(schemas)
