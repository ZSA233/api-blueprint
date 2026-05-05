from __future__ import annotations

import enum
import re
import shutil
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator, Optional, Set, Type

from api_blueprint.engine.group import RouterGroup
from api_blueprint.engine.model import Error, Null, create_model, iter_enum_classes, iter_model_vars
from api_blueprint.engine.provider import ProviderName
from api_blueprint.engine.router import Router
from api_blueprint.engine.utils import join_path_imports, pascal_to_snake_case, snake_to_pascal_case
from api_blueprint.engine.wrapper import NoneWrapper, ResponseWrapper
from api_blueprint.writer.core.base import BaseBlueprint
from api_blueprint.writer.core.templates import iter_render, render

from .common import LANG, PackageName, GolangType, internal_codegen_dir
from .protos import (
    GolangEnum,
    GolangPackageLayout,
    GolangProto,
    GolangProtoAlias,
    GolangProtoGeneric,
    GolangResponseWrapper,
    ensure_model,
)

if TYPE_CHECKING:
    from .writer import GolangWriter


def _route_slug(value: str, *, default: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z]+", "_", value.lower()).strip("_")
    return normalized or default


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
    def key(self) -> str:
        _cls_name, key = self._err.__key__
        return key.upper()


class GolangErrorGroup:
    def __init__(self, package: str, imports: str, gen_dir: str, errs: list[Error]):
        self.package = package
        self.imports = imports
        self.gen_dir = gen_dir
        self.errors = [GolangError(err) for err in errs]

    def error_vars(self) -> Generator[GolangError, None, None]:
        yield from self.errors


class GolangRouter:
    def __init__(self, router: Router):
        self.router = router

    @property
    def url(self):
        return self.router.url

    @property
    def methods(self) -> list[str]:
        return [method.upper() for method in self.router.methods]

    @property
    def root(self) -> str:
        return self.router.group.bp.root.strip("/") or "root"

    @property
    def group(self) -> str:
        return self.router.group.branch.strip("/")

    @property
    def namespace(self) -> str:
        return self._group_alias()

    @property
    def service_name(self) -> str:
        service_name = snake_to_pascal_case(self.namespace or "root", "", "Group")
        if not service_name.endswith("Service"):
            service_name += "Service"
        return service_name

    @property
    def route_id(self) -> str:
        root_slug = _route_slug(self.router.group.bp.root.strip("/"), default="root")
        method_slug = _route_slug(",".join(sorted(method.lower() for method in self.router.methods)), default="route")
        route_name_slug = _route_slug(self.func_name, default="root")
        return ".".join((root_slug, self.namespace, method_slug, route_name_slug))

    def _group_alias(self) -> str:
        branch = self.router.group.branch.strip("/")
        if branch:
            return _route_slug(branch, default="root")
        return _route_slug(self.router.group.root.strip("/"), default="root")

    @property
    def func_name(self):
        if not self.router.leaf.strip("/"):
            return "ROOT_"
        return snake_to_pascal_case(self.router.leaf, "", "Z")

    @property
    def ctx_type(self):
        return f"CTX_{self.func_name}"

    @property
    def req_type(self):
        return f"REQ_{self.func_name}"

    @property
    def rsp_type(self):
        return f"RSP_{self.func_name}"

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
    def local_query_type_expr(self) -> str:
        return self.query_alias_name or "any"

    @property
    def local_body_type_expr(self) -> str:
        return self.body_alias_name or "any"

    @property
    def executor_body_type_expr(self) -> str:
        if "WS" in self.methods:
            return "any"
        return self.local_body_type_expr

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
    def is_json_response(self) -> bool:
        return self.router.rsp_media_type == "application/json"

    @property
    def is_xml_response(self) -> bool:
        return self.router.rsp_media_type == "application/xml"

    @property
    def is_text_response(self) -> bool:
        return not self.is_json_response

    @property
    def response_wrapper_name(self) -> str:
        return self.router.response_wrapper.__name__

    @property
    def has_wrapped_json_response(self) -> bool:
        return self.is_json_response and self.router.response_wrapper is not NoneWrapper

    @property
    def req_provider(self):
        options = [
            ("Q", self.router.req_query),
            ("F", self.router.req_form),
            ("J", self.router.req_json),
        ]
        return "".join(value for value, ok in options if ok)

    @property
    def rsp_provider(self):
        media_type_mapping = {
            "application/json": "json",
            "application/xml": "xml",
            "text/html": "html",
        }
        return "@".join([
            media_type_mapping[self.router.rsp_media_type],
            self.router.response_wrapper.__name__,
        ])

    @property
    def providers(self):
        provider_specs: list[str] = []
        for provider in self.router.providers:
            data = provider.data
            if provider.name == ProviderName.REQ.value:
                data = self.req_provider
            elif provider.name == ProviderName.RSP.value:
                data = self.rsp_provider
            elif provider.name == ProviderName.WS_HANDLE.value:
                data = ",".join(data)

            key = provider.name
            if data:
                key += f"={data}"
            provider_specs.append(key)
        return "|".join(provider_specs)

    @property
    def http_raw_response(self) -> bool:
        return bool(self.router.extra.get("http_raw_response"))

    def protos(self) -> Generator[GolangProto, None, None]:
        req_query_proto = None
        req_form_proto = None
        req_json_proto = None

        if self.router.req_query is not None:
            req_query_proto = GolangProto.from_model_ref(ensure_model(self.router.req_query), f"{self.req_type}_QUERY")
            yield req_query_proto
        if self.router.req_form is not None:
            req_form_proto = GolangProto.from_model_ref(ensure_model(self.router.req_form), f"{self.req_type}_FORM")
            yield req_form_proto
        if self.router.req_json is not None:
            req_json_proto = GolangProto.from_model_ref(ensure_model(self.router.req_json), f"{self.req_type}_JSON")
            yield req_json_proto

        yield GolangProto(
            self.req_type,
            create_model(
                self.req_type,
                {
                    "Q": self.router.req_query,
                    "B": self.router.req_json or self.router.req_form or Null(),
                },
            ),
            "generic",
            generic=GolangProtoGeneric(
                name=GolangType("{provider_package$}REQ"),
                types=[req_query_proto or GolangType("any"), req_json_proto or req_form_proto or GolangType("any")],
            ),
        )

        rsp_json_proto = None
        if self.router.rsp_model is not None:
            rsp_json_proto = GolangProto.from_model_ref(ensure_model(self.router.rsp_model), f"{self.rsp_type}_BODY")
            yield rsp_json_proto

        yield GolangProto(
            self.rsp_type,
            self.router.rsp_model,
            "alias",
            alias=GolangProtoAlias(
                name=GolangType(rsp_json_proto.name if rsp_json_proto else "any"),
                proto=rsp_json_proto,
            ),
        )

        yield GolangProto(
            self.ctx_type,
            create_model(
                self.req_type,
                {
                    "Q": self.router.req_query or Null(),
                    "B": self.router.req_json or self.router.req_form or Null(),
                    "P": self.router.rsp_model or Null(),
                },
            ),
            "generic",
            generic=GolangProtoGeneric(
                name=GolangType("{provider_package$}Context"),
                types=[
                    req_query_proto or GolangType("any"),
                    req_json_proto or req_form_proto or GolangType("any"),
                    rsp_json_proto or GolangType("any"),
                ],
            ),
        )

    def com_protos(self) -> Generator[GolangProto, None, None]:
        if self.router.req_query is not None:
            yield from GolangProto.from_model(self.router.req_query).com_protos()
        if self.router.req_form is not None:
            yield from GolangProto.from_model(self.router.req_form).com_protos()
        if self.router.req_json is not None:
            yield from GolangProto.from_model(self.router.req_json).com_protos()
        if self.router.rsp_model is not None:
            yield from GolangProto.from_model(self.router.rsp_model).com_protos()
        for recv in self.router.recvs:
            yield from GolangProto.from_model(recv).com_protos()
        for send in self.router.sends:
            yield from GolangProto.from_model(send).com_protos()


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
        return self.branch if self.branch else self.root

    @property
    def package_leaf(self) -> str:
        return self.package.rsplit("/", 1)[-1]

    @property
    def export_name(self) -> str:
        return snake_to_pascal_case(self.package_leaf, "", "Z")

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
        imports = join_path_imports(self.bp.writer.http_adapter_imports, self.root)
        if self.branch:
            imports = join_path_imports(imports, self.package)
        return imports

    def __len__(self) -> int:
        return len(self.group)

    def interfaces(self) -> Generator[dict[str, Any], None, None]:
        for router in self.group:
            view = GolangRouter(router)
            yield {
                "func": view.func_name,
                "ctx_type": view.ctx_type,
                "req_type": view.req_type,
                "rsp_type": view.rsp_type,
            }

    def registers(self) -> Generator[dict[str, Any], None, None]:
        for router in self.group:
            view = GolangRouter(router)
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
                    "raw_response": view.http_raw_response,
                    "bind_query": view.bind_query,
                    "bind_json": view.bind_json,
                    "bind_form": view.bind_form,
                }

    def protos(self) -> Generator[GolangProto, None, None]:
        for router in self.group:
            yield from GolangRouter(router).protos()

    def com_protos(self) -> Generator[GolangProto, None, None]:
        for router in self.group:
            yield from GolangRouter(router).com_protos()

    def implements(self) -> Generator[dict[str, Any], None, None]:
        for router in self.group:
            view = GolangRouter(router)
            yield {
                "func": view.func_name,
                "ctx_type": view.ctx_type,
                "req_type": view.req_type,
                "rsp_type": view.rsp_type,
            }


class GolangBlueprint(BaseBlueprint["GolangWriter"]):
    router_groups: Optional[list[GolangRouterGroup]] = None

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
        return self.bp.root.strip("/")

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

    def formatters(self, update: Optional[dict[str, str]] = None) -> dict[str, str]:
        formatters = self.writer.formatters()
        formatters.update(
            {
                "enums_package": self.com_enum_package,
                "enums_imports": self.com_enum_imports,
                "protos_package": self.com_proto_package,
                "protos_imports": self.com_proto_imports,
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
        view_dir = self.writer.working_dir / self.writer.views_package / "routes" / self.package
        ctx = {"writer": self.writer, "bp": self}

        self.cleanup_legacy_http_files()

        with self.writer.write_file(view_dir / self.com_proto_gen_path / "protos.go", overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "protos.go", ctx, "views/_gen_protos"))

        enums_path = view_dir / self.com_enum_gen_path / "enums.go"
        with self.writer.write_file(enums_path, overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "enums.go", ctx, "views/_gen_enums"))
        self.writer.toolchain.run_go_enum(enums_path)

        with self.writer.write_file(view_dir / "gen_blueprint.go", overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "gen_blueprint.go", ctx, "views"))

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

    def gen_http_adapter(self) -> None:
        ctx = {"writer": self.writer, "bp": self}
        with self.writer.write_file(self.writer.http_transport_dir / "gen_engine.go", overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "gen_engine.go", ctx, "views/transports/http"))

        view_dir = self.writer.http_transport_dir / self.package
        with self.writer.write_file(view_dir / "gen_blueprint.go", overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "gen_blueprint.go", ctx, "views/transports/http"))

        for group in self.get_router_groups():
            self.gen_http_router(group)

    def validate_reserved_paths(self) -> None:
        self._validate_reserved_segments(self.package, label="blueprint root")
        for group in self.get_router_groups():
            if group.branch:
                self._validate_reserved_segments(group.branch, label="router group")

    def _validate_reserved_segments(self, raw_path: str, *, label: str) -> None:
        segments = [segment for segment in raw_path.strip("/").split("/") if segment]
        for segment in segments:
            if segment.startswith("_"):
                raise ValueError(
                    f"[gen_golang] {label}[{raw_path}] 使用了生成器保留目录段[{segment}]；"
                    "以下划线开头的 Go 目录由 api-blueprint 保留"
                )

    def gen_routers(self, group: GolangRouterGroup) -> None:
        view_dir = self.writer.working_dir / self.writer.views_package / "routes" / self.package / group.package
        ctx = {"writer": self.writer, "bp": self, "router_group": group}
        for name, text in iter_render(LANG, ctx, "views/route"):
            overwrite = name.startswith("gen_")
            path = view_dir / name if group.branch else view_dir.parent / name
            with self.writer.write_file(path, overwrite=overwrite) as handle:
                if handle:
                    handle.write(text)

    def gen_http_router(self, group: GolangRouterGroup) -> None:
        view_dir = self.writer.http_transport_dir / self.package
        if group.branch:
            view_dir /= group.package
        ctx = {"writer": self.writer, "bp": self, "router_group": group}
        for name, text in iter_render(LANG, ctx, "views/route/transports/http"):
            overwrite = name.startswith("gen_")
            with self.writer.write_file(view_dir / name, overwrite=overwrite) as handle:
                if handle:
                    handle.write(text)
