from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Generator, Optional, Set, Type

from api_blueprint.engine.group import RouterGroup
from api_blueprint.engine.model import Null, create_model, iter_enum_classes
from api_blueprint.engine.router import Router
from api_blueprint.engine.utils import join_path_imports
from api_blueprint.writer.core.base import BaseBlueprint, BaseWriter
from api_blueprint.writer.core.files import ensure_filepath_open
from api_blueprint.writer.core.templates import iter_render, render
from api_blueprint.writer.core.contracts import route_contract
from api_blueprint.writer.golang.blueprint import GolangRouter
from api_blueprint.writer.golang.common import GolangType
from api_blueprint.writer.golang.protos import (
    GolangEnum,
    GolangPackageLayout,
    GolangProto,
    GolangProtoAlias,
    GolangProtoGeneric,
    ensure_model,
)
from api_blueprint.writer.golang.toolchain import GolangToolchain


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("WailsGoWriter")
logger.setLevel(logging.INFO)

LANG = "wails"


class WailsRouter:
    def __init__(self, router: Router):
        self.router = router
        self.go = GolangRouter(router)
        self.contract = route_contract(router)

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

    def _query_proto(self) -> GolangProto | GolangType:
        if self.router.req_query is None:
            return GolangType("any")
        return GolangProto.from_model_ref(ensure_model(self.router.req_query), f"{self.req_type}_QUERY")

    def _body_proto(self) -> GolangProto | GolangType:
        req_body = self.router.req_json or self.router.req_form
        if req_body is None:
            return GolangType("any")
        suffix = "JSON" if self.router.req_json is not None else "FORM"
        return GolangProto.from_model_ref(ensure_model(req_body), f"{self.req_type}_{suffix}")

    def _rsp_proto(self) -> GolangProto | GolangType:
        if self.router.rsp_model is None:
            return GolangType("any")
        return GolangProto.from_model_ref(ensure_model(self.router.rsp_model), f"{self.rsp_type}_BODY")

    def _ws_recv_proto(self) -> GolangProto | GolangType:
        if len(self.router.recvs) != 1:
            return GolangType("any")
        return GolangProto.from_model_ref(ensure_model(self.router.recvs[0]), f"{self.ws_send_type}_BODY")

    @staticmethod
    def _type_name(proto: GolangProto | GolangType) -> str:
        if isinstance(proto, GolangProto):
            return proto.name
        return str(proto)

    @property
    def query_type_name(self) -> str:
        return self._type_name(self._query_proto())

    @property
    def body_type_name(self) -> str:
        return self._type_name(self._body_proto())

    @property
    def response_body_type_name(self) -> str:
        return self._type_name(self._rsp_proto())

    @property
    def ws_recv_type_name(self) -> str:
        return self._type_name(self._ws_recv_proto())

    def protos(self) -> Generator[GolangProto, None, None]:
        yield from self.go.protos()

        query_proto = self._query_proto()
        body_proto = self._body_proto()
        yield GolangProto(
            self.invoke_type,
            create_model(self.invoke_type, {}),
            "generic",
            generic=GolangProtoGeneric(
                name=GolangType("{provider_package$}InvokeEnvelope"),
                types=[query_proto, body_proto],
            ),
        )
        if self.has_ws:
            ws_recv_proto = self._ws_recv_proto()
            if isinstance(ws_recv_proto, GolangProto):
                yield ws_recv_proto
            yield GolangProto(
                self.ws_connect_type,
                create_model(self.ws_connect_type, {}),
                "generic",
                generic=GolangProtoGeneric(
                    name=GolangType("{provider_package$}InvokeEnvelope"),
                    types=[query_proto, GolangType("any")],
                ),
            )
            yield GolangProto(
                self.ws_send_type,
                create_model(self.ws_send_type, {}),
                "generic",
                generic=GolangProtoGeneric(
                    name=GolangType("{provider_package$}SocketSendEnvelope"),
                    types=[ws_recv_proto],
                ),
            )
            yield GolangProto(
                self.ws_close_type,
                create_model(self.ws_close_type, {}),
                "alias",
                alias=GolangProtoAlias(name=GolangType("{provider_package$}SocketCloseEnvelope")),
            )

    def com_protos(self) -> Generator[GolangProto, None, None]:
        yield from self.go.com_protos()


class WailsRouterGroup:
    def __init__(self, bp: "WailsBlueprint", group: RouterGroup):
        self.bp = bp
        self.group = group
        self._routers: Optional[list[Router]] = None

    @property
    def routers(self) -> list[Router]:
        if self._routers is None:
            self._routers = list(self.group)
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

    def __len__(self) -> int:
        return len(self.routers)

    def views(self) -> Generator[WailsRouter, None, None]:
        for router in self.routers:
            yield WailsRouter(router)

    def interfaces(self) -> Generator[dict[str, str], None, None]:
        for route in self.views():
            yield {
                "func": route.func_name,
                "ctx_type": route.ctx_type,
                "req_type": route.req_type,
                "rsp_type": route.rsp_type,
            }

    def protos(self) -> Generator[GolangProto, None, None]:
        for route in self.views():
            yield from route.protos()

    def com_protos(self) -> Generator[GolangProto, None, None]:
        for route in self.views():
            yield from route.com_protos()


class WailsBlueprint(BaseBlueprint["WailsGoWriter"]):
    def __init__(self, writer: "WailsGoWriter", bp):
        super().__init__(writer, bp)
        self.router_groups: Optional[list[WailsRouterGroup]] = None

    @property
    def package(self) -> str:
        return self.bp.root.strip("/")

    @property
    def imports(self) -> str:
        return join_path_imports(self.writer.module_import, self.package)

    @property
    def com_proto_package(self) -> str:
        return "protos"

    @property
    def com_proto_gen_path(self) -> str:
        return "gen-protos"

    @property
    def com_proto_imports(self) -> str:
        return join_path_imports(self.imports, self.com_proto_gen_path)

    @property
    def com_enum_package(self) -> str:
        return "enums"

    @property
    def com_enum_gen_path(self) -> str:
        return "gen-enums"

    @property
    def com_enum_imports(self) -> str:
        return join_path_imports(self.imports, self.com_enum_gen_path)

    def get_router_groups(self) -> list[WailsRouterGroup]:
        if self.router_groups is None:
            group_set: Set[RouterGroup] = set()
            groups = []
            for group, _router in self.iter_router():
                if group in group_set:
                    continue
                group_set.add(group)
                groups.append(WailsRouterGroup(self, group))
            self.router_groups = groups
        return self.router_groups

    def formatters(self, update: Optional[dict[str, str]] = None) -> dict[str, str]:
        formatters = self.writer.formatters()
        formatters.update(
            {
                "protos_package": self.com_proto_package,
                "protos_imports": self.com_proto_imports,
                "enums_package": self.com_enum_package,
                "enums_imports": self.com_enum_imports,
            }
        )
        formatters.update({key + "$": value + "." for key, value in formatters.items() if key.endswith("_package")})
        if update:
            formatters.update(update)
        return formatters

    def protos(self) -> Generator[GolangProto, None, None]:
        seen: set[str] = set()
        for group in self.get_router_groups():
            for proto in group.protos():
                if proto.name in seen:
                    continue
                seen.add(proto.name)
                yield proto

    def com_protos(self) -> Generator[GolangProto, None, None]:
        seen: set[str] = set()
        for group in self.get_router_groups():
            for proto in group.com_protos():
                if proto.name in seen:
                    continue
                seen.add(proto.name)
                yield proto

    def com_enums(self) -> Generator[GolangEnum, None, None]:
        seen: set[Type[object]] = set()
        for proto in self.com_protos():
            for enum_cls in iter_enum_classes(proto.model_type):
                if enum_cls in seen:
                    continue
                golang_enum = GolangEnum.from_enum(enum_cls)
                if golang_enum is None:
                    continue
                seen.add(enum_cls)
                yield golang_enum

    def gen(self) -> None:
        ctx = {"writer": self.writer, "bp": self}

        runtime_dir = self.writer.working_dir / self.writer.runtime_package
        for name, text in iter_render(LANG, ctx, "runtime"):
            overwrite = name.startswith("gen_")
            with self.writer.write_file(runtime_dir / name, overwrite=overwrite) as handle:
                if handle:
                    handle.write(text)

        package_dir = self.writer.working_dir / self.package
        with self.writer.write_file(package_dir / self.com_proto_gen_path / "protos.go", overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "protos.go", ctx, "go/protos"))

        enums_path = package_dir / self.com_enum_gen_path / "enums.go"
        with self.writer.write_file(enums_path, overwrite=True) as handle:
            if handle:
                handle.write(render(LANG, "enums.go", ctx, "go/enums"))
        self.writer.toolchain.run_go_enum(enums_path)

        for group in self.get_router_groups():
            self.gen_group(group)

    def gen_group(self, group: WailsRouterGroup) -> None:
        base_dir = self.writer.working_dir / self.package
        group_dir = base_dir if not group.branch else base_dir / group.package
        ctx = {"writer": self.writer, "bp": self, "router_group": group}
        for name, text in iter_render(LANG, ctx, "go/route"):
            overwrite = name.startswith("gen_")
            with self.writer.write_file(group_dir / name, overwrite=overwrite) as handle:
                if handle:
                    handle.write(text)


class WailsGoWriter(BaseWriter[WailsBlueprint]):
    def __init__(
        self,
        working_dir: str | Path = ".",
        *,
        version: str,
        module: str | None = None,
        runtime_package: str = "runtime",
    ):
        super().__init__(working_dir)
        self.version = version
        self.runtime_package = runtime_package
        self.toolchain = GolangToolchain(logger)
        self._written_files: Set[str] = set()

        gmods = self.toolchain.read_gomodule(working_dir)
        if len(gmods) > 1 and not module:
            raise ModuleNotFoundError(f"[wails] 路径下存在多个 module，需要使用 module 指定其一: {[key for key, _ in gmods]}")

        self.module_import: str | None = None
        for mod, mod_dir in gmods:
            if mod == "command-line-arguments":
                raise ModuleNotFoundError("[wails] 生成目录找不到 gomodule，无法继续生成 wails go 代码")
            if not module or module == mod:
                module = mod
                self.module_import = (Path(module) / Path(working_dir).absolute().relative_to(mod_dir)).as_posix()
                logger.info("[*] gomodule: %s", module)
                break

        if self.module_import is None:
            raise ModuleNotFoundError(f"[wails] 生成目录找不到 gomodule[{module}]，无法继续生成 wails go 代码")

    @property
    def runtime_imports(self) -> str:
        return join_path_imports(self.module_import, self.runtime_package)

    def formatters(self, update: Optional[dict[str, str]] = None) -> dict[str, str]:
        formatters = {
            "provider_package": self.runtime_package,
            "provider_imports": self.runtime_imports,
        }
        formatters.update({key + "$": value + "." for key, value in formatters.items() if key.endswith("_package")})
        if update:
            formatters.update(update)
        return formatters

    def gen(self) -> None:
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
