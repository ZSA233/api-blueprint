from __future__ import annotations

import logging
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Generator, Literal, Mapping, Optional, Sequence, Set

from api_blueprint.engine.connection import ConnectionKind
from api_blueprint.engine.model import iter_error_models, iter_model_vars
from api_blueprint.engine.router import Router
from api_blueprint.engine.utils import join_path_imports, pascal_to_snake_case
from api_blueprint.engine.wrapper import ResponseWrapper
from api_blueprint.writer.core.base import BaseWriter
from api_blueprint.writer.core.contract_adapters import RouteContractIndex, RouteProtocolContract
from api_blueprint.writer.core.contracts import RouteContract
from api_blueprint.writer.core.files import ensure_filepath_open
from api_blueprint.writer.core.templates import iter_render

from .blueprint import GolangBlueprint, GolangErrorGroup
from .common import LANG, PackageName
from .protos import GolangPackageLayout, GolangResponseWrapper
from .toolchain import GolangToolchain

if TYPE_CHECKING:
    from api_blueprint.contract import ContractGraph

GolangTransportKind = Literal["http"]
DEFAULT_GOLANG_TRANSPORTS: tuple[GolangTransportKind, ...] = ("http",)


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("GolangWriter")
logger.setLevel(logging.INFO)


class GolangWriter(BaseWriter[GolangBlueprint]):
    def __init__(
        self,
        working_dir: str = ".",
        *,
        module: Optional[str] = None,
        views_package: str = "",
        errors_package: str = "runtime/errors",
        enabled_transports: Sequence[GolangTransportKind] = DEFAULT_GOLANG_TRANSPORTS,
        contract_graph: ContractGraph | None = None,
        **kwargs: dict[str, Any],
    ):
        super().__init__(working_dir)

        self.toolchain = GolangToolchain(logger)
        self._written_files: Set[str] = set()
        self._response_wrappers: Optional[list[type[ResponseWrapper]]] = None
        self._list_providers_cache: Optional[set[str]] = None

        resolved_module = self.toolchain.resolve_module_import(working_dir, module=module, label="[go]")
        self.gomodule = resolved_module.module
        self.gomodpath = resolved_module.import_path
        logger.info("[*] gomodule: %s", self.gomodule)

        self.packages = GolangPackageLayout(
            module_import=self.gomodpath,
            views_package=views_package,
            errors_package=errors_package,
        )
        self.views_package = self.packages.views_package
        self.provider_package = self.packages.provider_package
        self.errors_package = self.packages.errors_package
        self.route_contract_index = RouteContractIndex.from_graph(contract_graph) if contract_graph is not None else None
        self.enabled_transports = tuple(enabled_transports)
        unknown_transports = sorted(set(self.enabled_transports) - {"http"})
        if unknown_transports:
            raise ValueError(
                "GolangWriter enabled_transports contains unsupported values: "
                + ", ".join(unknown_transports)
            )

    def validate_package_contract(self) -> None:
        return None

    def _ensure_route_contract_index(self) -> RouteContractIndex:
        if self.route_contract_index is None:
            from api_blueprint.contract import build_contract_graph

            self.route_contract_index = RouteContractIndex.from_graph(build_contract_graph([bp.bp for bp in self.bps]))
        return self.route_contract_index

    def route_contract_for(self, router: Router) -> RouteContract:
        return self._ensure_route_contract_index().protocol_for_router(router).route

    def route_protocol_for(self, router: Router) -> RouteProtocolContract:
        return self._ensure_route_contract_index().protocol_for_router(router)

    @property
    def views_imports(self) -> str:
        return self.packages.views_imports

    @property
    def routes_imports(self) -> str:
        return self.packages.routes_imports

    @property
    def provider_imports(self) -> str:
        return self.packages.provider_imports

    @property
    def errors_imports(self) -> str:
        return self.packages.errors_imports

    @property
    def http_adapter_enabled(self) -> bool:
        return "http" in self.enabled_transports

    @property
    def http_transport_imports(self) -> str:
        return join_path_imports(self.views_imports, "transports", "http")

    @property
    def http_adapter_imports(self) -> str:
        return join_path_imports(self.views_imports, "transports", "http")

    @property
    def http_transport_dir(self) -> Path:
        return self.working_dir / self.views_package / "transports" / "http"

    def list_providers(self) -> set[str]:
        if self._list_providers_cache is None:
            self._list_providers_cache = {
                provider.name
                for bp in self.bps
                for group in bp.get_router_groups()
                for router in group.routers
                for provider in router.providers
            }
        return self._list_providers_cache

    def has_stream_routes(self) -> bool:
        return any(
            router.connection_kind == ConnectionKind.STREAM
            for bp in self.bps
            for group in bp.get_router_groups()
            for router in group.routers
        )

    def has_channel_routes(self) -> bool:
        return any(
            router.connection_kind == ConnectionKind.CHANNEL
            for bp in self.bps
            for group in bp.get_router_groups()
            for router in group.routers
        )

    def has_connection_routes(self) -> bool:
        return self.has_stream_routes() or self.has_channel_routes()

    def needs_websocket_runtime(self) -> bool:
        return "ws_handle" in self.list_providers() or self.has_channel_routes()

    def formatters(self, update: Optional[dict[str, str]] = None) -> dict[str, str]:
        return self.packages.formatters(update)

    def error_vars(self) -> Generator[GolangErrorGroup, None, None]:
        used_error_models = self._used_error_model_names()
        for cls_name, cls in iter_error_models():
            if cls_name not in used_error_models:
                continue
            err_pkg = pascal_to_snake_case(cls_name)
            err_imports = join_path_imports(self.errors_imports, err_pkg)
            err_dir = Path(self.working_dir / self.errors_package / err_pkg)
            errors = [field for _name, field in iter_model_vars(cls) if getattr(field, "__type__", None) == "error"]
            yield GolangErrorGroup(err_pkg, err_imports, err_dir, errors)

    def _used_error_model_names(self) -> set[str]:
        names: set[str] = set()
        for bp in self.bps:
            self._collect_error_model_names(names, bp.bp.errors)
            for _group, router in bp.bp.iter_router():
                self._collect_error_model_names(names, router.errors)
        return names

    @staticmethod
    def _collect_error_model_names(names: set[str], errors_by_code: Mapping[int, list[Any]]) -> None:
        for errors in errors_by_code.values():
            for err in errors:
                key = getattr(err, "__key__", None)
                if key:
                    names.add(key[0])

    def response_wrappers(self, *prefixes: str) -> Generator[GolangResponseWrapper, None, None]:
        if self._response_wrappers is None:
            wrappers = set()
            for bp in self.bps:
                for group in bp.get_router_groups():
                    for router in group.routers:
                        wrappers.add(router.response_wrapper)
            self._response_wrappers = sorted(wrappers, key=lambda wrapper: wrapper.__name__)

        for prefix in prefixes:
            for wrapper in self._response_wrappers:
                yield GolangResponseWrapper(prefix=prefix, response_wrapper=wrapper)

    def gen(self) -> None:
        self.validate_package_contract()
        self.cleanup_legacy_output_roots()
        for bp in self.bps:
            bp.build()
            bp.gen_views()

        self.gen_errors()
        self.gen_providers()

        if self._written_files:
            for file in self._written_files:
                self.toolchain.run_format(file)

    def cleanup_legacy_output_roots(self) -> None:
        if self.views_package:
            return
        legacy_views_dir = self.working_dir / PackageName.VIEWS.value
        if self._looks_like_legacy_generated_go_root(legacy_views_dir):
            shutil.rmtree(legacy_views_dir)
        for legacy_errors_dir in (self.working_dir / PackageName.ERROR.value, self.working_dir.parent / PackageName.ERROR.value):
            if self._looks_like_legacy_generated_errors_dir(legacy_errors_dir):
                shutil.rmtree(legacy_errors_dir)

    @staticmethod
    def _looks_like_legacy_generated_go_root(path: Path) -> bool:
        if not path.is_dir():
            return False
        return any((path / name).exists() for name in ("routes", "providers", "transports", "engine.go"))

    @staticmethod
    def _looks_like_legacy_generated_errors_dir(path: Path) -> bool:
        if not path.is_dir():
            return False
        if (path / "gen_errors.go").is_file():
            return True
        base_file = path / "errors.go"
        if base_file.is_file():
            text = base_file.read_text(encoding="utf-8")
            if "type CodeErrInterface interface" in text or "func New(code int, message string) *Error" in text:
                return True
        return any(child.is_dir() and (child / "gen_errors.go").is_file() for child in path.iterdir())

    def gen_errors(self) -> None:
        for error_group in self.error_vars():
            for name, text in iter_render(LANG, {"writer": self, "error_group": error_group}, "errors/group"):
                overwrite = name.startswith("gen_")
                with self.write_file(error_group.gen_dir / name, overwrite=overwrite) as handle:
                    if handle:
                        handle.write(text)

        errors_dir = self.working_dir / self.errors_package
        self.cleanup_stale_root_error_catalog(errors_dir)
        for name, text in iter_render(LANG, {"writer": self}, "errors"):
            overwrite = name.startswith("gen_")
            with self.write_file(errors_dir / name, overwrite=overwrite) as handle:
                if handle:
                    handle.write(text)

    @staticmethod
    def cleanup_stale_root_error_catalog(errors_dir: Path) -> None:
        stale_catalog = errors_dir / "gen_error_catalog.go"
        if not stale_catalog.is_file():
            return
        text = stale_catalog.read_text(encoding="utf-8")
        if text.startswith("// Code generated by api-blueprint") and "CatalogByID" in text:
            stale_catalog.unlink()

    def gen_providers(self) -> None:
        provider_dir = self.working_dir / self.views_package / self.provider_package
        for name, text in iter_render(LANG, {"writer": self}, "provider"):
            overwrite = name.startswith("gen_")
            with self.write_file(provider_dir / name, overwrite=overwrite) as handle:
                if handle:
                    handle.write(text)

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
