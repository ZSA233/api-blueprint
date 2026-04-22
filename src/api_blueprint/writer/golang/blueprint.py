from __future__ import annotations

import enum
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator, Optional, Set, Type

from api_blueprint.engine.group import RouterGroup
from api_blueprint.engine.model import Error, Null, create_model, iter_enum_classes, iter_model_vars
from api_blueprint.engine.provider import ProviderName
from api_blueprint.engine.router import Router
from api_blueprint.engine.utils import join_path_imports, pascal_to_snake_case, snake_to_pascal_case
from api_blueprint.engine.wrapper import ResponseWrapper
from api_blueprint.writer.core.base import BaseBlueprint
from api_blueprint.writer.core.templates import iter_render, render

from .common import LANG, PackageName, GolangType
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
    def root(self) -> str:
        return self.group.bp.root.strip("/")

    @property
    def branch(self) -> str:
        return self.group.branch.strip("/")

    @property
    def imports(self) -> str:
        return self.bp.imports if not self.branch else join_path_imports(self.bp.imports, self.package)

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
    def package(self) -> str:
        return self.bp.root.strip("/")

    @property
    def imports(self) -> str:
        return join_path_imports(self.writer.views_imports, self.package)

    @property
    def com_proto_package(self) -> str:
        return PackageName.COM_PROTOS.value

    @property
    def com_proto_gen_path(self) -> str:
        return f"gen-{self.com_proto_package}"

    @property
    def com_proto_imports(self) -> str:
        return join_path_imports(self.imports, self.com_proto_gen_path)

    @property
    def com_enum_package(self) -> str:
        return PackageName.COM_ENUMS.value

    @property
    def com_enum_gen_path(self) -> str:
        return f"gen-{self.com_enum_package}"

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
        view_dir = self.writer.working_dir / self.writer.views_package / self.package
        ctx = {"writer": self.writer, "bp": self}

        with self.writer.write_file(self.writer.working_dir / self.writer.views_package / "engine.go") as handle:
            if handle:
                handle.write(render(LANG, "engine.go", ctx, ""))

        with self.writer.write_file(view_dir / self.com_proto_gen_path / "protos.go", overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "protos.go", ctx, "views/gen-protos"))

        enums_path = view_dir / self.com_enum_gen_path / "enums.go"
        with self.writer.write_file(enums_path, overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "enums.go", ctx, "views/gen-enums"))
        self.writer.toolchain.run_go_enum(enums_path)

        with self.writer.write_file(view_dir / "gen_blueprint.go", overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "gen_blueprint.go", ctx, "views"))

        for group in self.get_router_groups():
            self.gen_routers(group)

    def gen_routers(self, group: GolangRouterGroup) -> None:
        view_dir = self.writer.working_dir / self.writer.views_package / self.package / group.package
        ctx = {"writer": self.writer, "bp": self, "router_group": group}
        for name, text in iter_render(LANG, ctx, "views/route"):
            overwrite = name.startswith("gen_")
            path = view_dir / name if group.branch else view_dir.parent / name
            with self.writer.write_file(path, overwrite=overwrite) as handle:
                if handle:
                    handle.write(text)
