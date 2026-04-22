from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any, Generator, Optional, Set

from api_blueprint.engine.model import iter_error_models, iter_model_vars
from api_blueprint.engine.utils import join_path_imports, pascal_to_snake_case
from api_blueprint.engine.wrapper import ResponseWrapper
from api_blueprint.writer.core.base import BaseWriter
from api_blueprint.writer.core.files import ensure_filepath_open
from api_blueprint.writer.core.templates import iter_render

from .blueprint import GolangBlueprint, GolangErrorGroup
from .common import LANG, PackageName
from .protos import GolangPackageLayout, GolangResponseWrapper
from .toolchain import GolangToolchain


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("GolangWriter")
logger.setLevel(logging.INFO)


class GolangWriter(BaseWriter[GolangBlueprint]):
    def __init__(
        self,
        working_dir: str = ".",
        *,
        module: Optional[str] = None,
        views_package: str = PackageName.VIEWS.value,
        provider_package: str = PackageName.PROVIDER.value,
        errors_package: str = PackageName.ERROR.value,
        **kwargs: dict[str, Any],
    ):
        super().__init__(working_dir)

        self.toolchain = GolangToolchain(logger)
        self._written_files: Set[str] = set()
        self._response_wrappers: Optional[list[type[ResponseWrapper]]] = None
        self._list_providers_cache: Optional[set[str]] = None

        gmods = self.toolchain.read_gomodule(working_dir)
        if len(gmods) > 1 and not module:
            raise ModuleNotFoundError(f"[go]路径下存在多个module，需要使用module指定其一:{[key for key, _ in gmods]}")

        self.gomodule = None
        self.gomodpath = None
        for mod, mod_dir in gmods:
            if mod == "command-line-arguments":
                raise ModuleNotFoundError("[go]生成目录找不到gomodule，无法继续生成go代码")
            if not module or module == mod:
                module = mod
                self.gomodule = mod
                self.gomodpath = (Path(module) / Path(working_dir).absolute().relative_to(mod_dir)).as_posix()
                logger.info("[*] gomodule: %s", module)
                break

        if self.gomodpath is None:
            raise ModuleNotFoundError(f"[go]生成目录找不到gomodule[{module}]，无法继续生成go代码")

        self.packages = GolangPackageLayout(
            module_import=self.gomodpath,
            views_package=views_package,
            provider_package=provider_package,
            errors_package=errors_package,
        )
        self.views_package = self.packages.views_package
        self.provider_package = self.packages.provider_package
        self.errors_package = self.packages.errors_package

    @property
    def views_imports(self) -> str:
        return self.packages.views_imports

    @property
    def provider_imports(self) -> str:
        return self.packages.provider_imports

    @property
    def errors_imports(self) -> str:
        return self.packages.errors_imports

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

    def formatters(self, update: Optional[dict[str, str]] = None) -> dict[str, str]:
        return self.packages.formatters(update)

    def error_vars(self) -> Generator[GolangErrorGroup, None, None]:
        for cls_name, cls in iter_error_models():
            err_pkg = pascal_to_snake_case(cls_name)
            err_imports = join_path_imports(self.errors_imports, err_pkg)
            err_dir = Path(self.working_dir / self.errors_package / err_pkg)
            errors = [field for _name, field in iter_model_vars(cls) if getattr(field, "__type__", None) == "error"]
            yield GolangErrorGroup(err_pkg, err_imports, err_dir, errors)

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
        for bp in self.bps:
            bp.build()
            bp.gen_views()

        self.gen_errors()
        self.gen_providers()

        if self._written_files:
            for file in self._written_files:
                self.toolchain.run_format(file)

    def gen_errors(self) -> None:
        for error_group in self.error_vars():
            for name, text in iter_render(LANG, {"writer": self, "error_group": error_group}, "errors/group"):
                overwrite = name.startswith("gen_")
                with self.write_file(error_group.gen_dir / name, overwrite=overwrite) as handle:
                    if handle:
                        handle.write(text)

        errors_dir = self.working_dir / self.errors_package
        for name, text in iter_render(LANG, {"writer": self}, "errors"):
            overwrite = name.startswith("gen_")
            with self.write_file(errors_dir / name, overwrite=overwrite) as handle:
                if handle:
                    handle.write(text)

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
