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

from api_blueprint.writer.golang.message_files import cleanup_stale_go_message_files, plan_go_message_files
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
    def group(self) -> str:
        cls_name, _key = self._err.__key__
        return cls_name

    @property
    def raw_key(self) -> str:
        _cls_name, key = self._err.__key__
        return key

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
        return self.group.bp.root_slug

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
                    "default_filename": view.protocol.response.filename or "",
                    "is_stream": view.is_stream,
                    "is_channel": view.is_channel,
                    "is_connection": view.is_connection,
                    "raw_response": view.http_raw_response,
                    "bind_query": view.bind_query,
                    "bind_json": view.bind_json,
                    "bind_form": view.bind_form,
                    "bind_multipart": view.bind_multipart,
                    "bind_binary": view.bind_binary,
                    "binary_content_encodings": (
                        list(view.protocol.request.binary_schema.content_encoding)
                        if view.protocol.request.binary_schema is not None
                        else []
                    ),
                }

    def protos(self) -> Generator[GolangProto, None, None]:
        for router in self.group:
            yield from self._router_view(router).protos()

    def com_protos(self) -> Generator[GolangProto, None, None]:
        for router in self.group:
            yield from self._router_view(router).com_protos()

    def binary_schemas(self) -> list[Any]:
        schemas = [
            schema
            for router in self.group
            for schema in (router.req_binary_schema, router.rsp_binary_schema)
            if schema is not None
        ]
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
                "connection_scaffold": view.connection_scaffold() is not None,
            }

    def user_implements(self) -> Generator[dict[str, Any], None, None]:
        for impl in self.implements():
            if impl["connection_scaffold"]:
                continue
            yield impl

    def message_unions(self) -> Generator[dict[str, Any], None, None]:
        seen: set[str] = set()
        for router in self.group:
            for union in self._router_view(router).message_unions():
                name = union["name"]
                if name in seen:
                    continue
                seen.add(name)
                yield union

    def connection_aliases(self) -> Generator[dict[str, str], None, None]:
        for router in self.group:
            alias = self._router_view(router).connection_alias()
            if alias is not None:
                yield alias

    def client_message_cases(self) -> Generator[dict[str, Any], None, None]:
        seen: set[str] = set()
        for router in self.group:
            cases = self._router_view(router).client_message_cases()
            if cases is None:
                continue
            name = cases["name"]
            if name in seen:
                continue
            seen.add(name)
            yield cases

    def connection_scaffolds(self) -> Generator[dict[str, Any], None, None]:
        for router in self.group:
            scaffold = self._router_view(router).connection_scaffold()
            if scaffold is not None:
                yield scaffold

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
        return to_go_package_path(self.bp.root_slug, fallback="root")

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
        self.cleanup_legacy_type_files(view_dir)
        self.cleanup_binary_codegen_dirs(view_dir)

        with self.writer.write_file(view_dir / self.com_proto_gen_path / "types.go", overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "types.go", ctx, "server/views/_gen_types"))

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

        self.gen_contract_metadata(view_dir)

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
        if legacy_http_runtime.exists() and not self._has_http_root_package("runtime"):
            shutil.rmtree(legacy_http_runtime)
        if self.writer.http_adapter_enabled:
            return
        transports_http = views_dir / "transports" / "http"
        if transports_http.exists():
            shutil.rmtree(transports_http)

    def _has_http_root_package(self, root_package: str) -> bool:
        return any(bp.root_package == root_package for bp in self.writer.bps)

    def cleanup_binary_codegen_dirs(self, view_dir: Path) -> None:
        for binary_dir in sorted(view_dir.rglob(self.binary_gen_path), key=lambda path: len(path.parts), reverse=True):
            if binary_dir.is_dir():
                shutil.rmtree(binary_dir)
        legacy_runtime_dir = view_dir / "_gen_binary_runtime"
        if legacy_runtime_dir.exists():
            shutil.rmtree(legacy_runtime_dir)

    def cleanup_legacy_type_files(self, view_dir: Path) -> None:
        legacy_shared_dir = view_dir / "_gen_protos"
        if legacy_shared_dir.exists():
            shutil.rmtree(legacy_shared_dir)
        if not view_dir.exists():
            return
        for legacy_file in view_dir.rglob("gen_protos.go"):
            if legacy_file.is_file():
                legacy_file.unlink()

    def gen_http_adapter(self) -> None:
        ctx = {"writer": self.writer, "bp": self}
        plan = build_go_server_blueprint_plan(self.writer, self)
        with self.writer.write_file(self.writer.http_transport_dir / "gen_config.go", overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "gen_config.go", ctx, "server/views/transports/http"))
        with self.writer.write_file(self.writer.http_transport_dir / "gen_engine.go", overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "gen_engine.go", ctx, "server/views/transports/http"))
        with self.writer.write_file(
            self.writer.http_transport_dir / "gen_connection_hooks.go",
            overwrite=True,
        ) as handle:
            if handle:
                handle.write(render(LANG, "gen_connection_hooks.go", ctx, "server/views/transports/http"))
        with self.writer.write_file(
            self.writer.http_transport_dir / "connection_hooks.go",
            overwrite=False,
        ) as handle:
            if handle:
                handle.write(render(LANG, "connection_hooks.go", ctx, "server/views/transports/http"))
        if self.writer.has_stream_routes():
            with self.writer.write_file(self.writer.http_transport_dir / "gen_stream.go", overwrite=True) as handle:
                if handle:
                    handle.write(render(LANG, "gen_stream.go", ctx, "server/views/transports/http"))
        else:
            self.cleanup_generated_http_transport_file("gen_stream.go")
        if self.writer.has_channel_routes():
            with self.writer.write_file(self.writer.http_transport_dir / "gen_channel.go", overwrite=True) as handle:
                if handle:
                    handle.write(render(LANG, "gen_channel.go", ctx, "server/views/transports/http"))
        else:
            self.cleanup_generated_http_transport_file("gen_channel.go")

        with self.writer.write_file(plan.http_root_dir / "gen_blueprint.go", overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "gen_blueprint.go", ctx, "server/views/transports/http"))

        for group in self.get_router_groups():
            self.gen_http_router(group)

    def cleanup_generated_http_transport_file(self, name: str) -> None:
        path = self.writer.http_transport_dir / name
        if not path.is_file():
            return
        text = path.read_text(encoding="utf-8")
        if text.startswith("// Code generated by api-blueprint"):
            path.unlink()

    def validate_reserved_paths(self) -> None:
        self._validate_reserved_segments(self.bp.root_slug, label="blueprint name")
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
        message_unions = list(group.message_unions())
        client_message_cases = list(group.client_message_cases())
        connection_scaffolds = list(group.connection_scaffolds())
        ctx = {
            "writer": self.writer,
            "bp": self,
            "router_group": group,
            "message_unions": message_unions,
            "client_message_cases": client_message_cases,
            "connection_scaffolds": connection_scaffolds,
        }
        self.gen_binary_router(group, plan.route_dir)
        message_files = plan_go_message_files(message_unions, client_message_cases)
        cleanup_stale_go_message_files(plan.route_dir, keep={message_file.filename for message_file in message_files})
        for message_file in message_files:
            with self.writer.write_file(plan.route_dir / message_file.filename, overwrite=True) as handle:
                if handle:
                    handle.write(
                        render(
                            LANG,
                            message_file.template_name,
                            {
                                **message_file.context,
                                "generated_label": "Go server",
                                "package_name": group.package,
                            },
                            "message",
                        )
                    )
        exclusives: tuple[str, ...] = ()
        if not self.writer.emit_impl_stubs:
            exclusives = (*exclusives, "impl.go")
            stale_impl = plan.route_dir / "impl.go"
            if stale_impl.exists() and self._looks_like_generated_user_stub(stale_impl):
                stale_impl.unlink()
        if not self.writer.emit_contract_metadata or not group.branch:
            exclusives = (*exclusives, "gen_contract.go")
            self.writer.cleanup_generated_file(plan.route_dir / "gen_contract.go")
        for name, text in iter_render(LANG, ctx, "server/views/route", exclusives=exclusives):
            overwrite = name.startswith("gen_")
            with self.writer.write_file(plan.route_dir / name, overwrite=overwrite) as handle:
                if handle:
                    handle.write(text)
        for scaffold in connection_scaffolds:
            scaffold_ctx = {**ctx, "scaffold": scaffold}
            for template_name, output_name in (
                ("session.go", scaffold["session_file"]),
                ("processor.go", scaffold["processor_file"]),
                ("error.go", scaffold["error_file"]),
            ):
                with self.writer.write_file(plan.route_dir / output_name, overwrite=False) as handle:
                    if handle:
                        handle.write(render(LANG, template_name, scaffold_ctx, "server/views/route/scaffold"))

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

    def gen_contract_metadata(self, view_dir: Path) -> None:
        contract_path = view_dir / "gen_contract.go"
        if not self.writer.emit_contract_metadata:
            self.writer.cleanup_generated_file(contract_path)
            return
        ctx = {"writer": self.writer, "bp": self}
        with self.writer.write_file(contract_path, overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "gen_contract.go", ctx, "server/views"))

    @staticmethod
    def _looks_like_generated_user_stub(path: Path) -> bool:
        if not path.is_file():
            return False
        text = path.read_text(encoding="utf-8")
        return "type Router struct" in text and "_GenRouter" in text and "not implemented" in text

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
            if router.rsp_binary_schema is not None:
                schemas.append(router.rsp_binary_schema)
        return unique_go_binary_schemas(schemas)
