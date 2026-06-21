from __future__ import annotations

from dataclasses import dataclass
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Union


@dataclass(frozen=True)
class ResolvedGoModule:
    module: str
    module_dir: Path
    import_path: str


class GolangToolchain:
    GO_ENUM_ARGS: Tuple[str, ...] = (
        "--names",
        "--values",
        "--mustparse",
        "--nocase",
        "--output-suffix",
        "_gen",
    )

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    @staticmethod
    def read_gomodule(path: str | Path) -> list[tuple[str, str]]:
        try:
            process = subprocess.run(
                ["go", "list", "-m", "-f", "{{.Path}} {{.Dir}}"],
                cwd=path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
            )
        except FileNotFoundError:
            module = GolangToolchain.read_gomod_file(path)
            if module is not None:
                return [module]
            raise
        except subprocess.CalledProcessError as exc:
            output = exc.stderr.strip() or exc.stdout.strip() or "unknown go list -m failure"
            raise ModuleNotFoundError(
                f"{output}\n"
                "提示: 当前目录可能受 go.work / workspace 影响。"
                " 如需按独立 module 解析，请尝试使用 `GOWORK=off go list -m -f \"{{.Path}} {{.Dir}}\"` 验证。"
            ) from exc
        modules: list[tuple[str, str]] = []
        for raw_line in process.stdout.splitlines():
            if not raw_line.strip():
                continue
            mod, sep, mod_dir = raw_line.partition(" ")
            if not sep:
                mod_dir = ""
            else:
                mod_dir = mod_dir.lstrip()
            modules.append((mod, mod_dir))
        return modules

    @staticmethod
    def read_gomod_file(path: str | Path) -> tuple[str, str] | None:
        current = Path(path).resolve()
        search_from = current if current.is_dir() else current.parent
        for directory in (search_from, *search_from.parents):
            gomod = directory / "go.mod"
            if not gomod.exists():
                continue
            for raw_line in gomod.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line.startswith("module "):
                    continue
                module = line.removeprefix("module ").strip()
                if module:
                    return module, str(directory)
                break
        return None

    def resolve_module_import(
        self,
        path: str | Path,
        *,
        module: str | None = None,
        label: str,
    ) -> ResolvedGoModule:
        if module == "":
            module = None
        working_dir = Path(path).resolve()
        gmods = self.read_gomodule(working_dir)
        if len(gmods) > 1 and not module:
            raise ModuleNotFoundError(
                f"{label} 路径下存在多个 module，需要使用 module 指定其一: {[key for key, _ in gmods]}。"
                " 如果这不是预期结果，请检查 go.work，必要时可先用 `GOWORK=off` 验证。"
            )

        for mod, mod_dir in gmods:
            if mod == "command-line-arguments":
                raise ModuleNotFoundError(
                    f"{label} 生成目录找不到 gomodule，无法继续生成。"
                    " 如果当前目录在 go.work 下，请先确认 `go list -m` 的解析结果，必要时使用 `GOWORK=off`。"
                )
            if module is not None and module != mod:
                continue
            module_dir = Path(mod_dir).resolve()
            return ResolvedGoModule(
                module=mod,
                module_dir=module_dir,
                import_path=(Path(mod) / working_dir.relative_to(module_dir)).as_posix(),
            )

        raise ModuleNotFoundError(
            f"{label} 生成目录找不到 gomodule[{module}]，无法继续生成。"
            " 如果目录由 go.work 管理，请确认目标 module 是否被 workspace 覆盖，必要时使用 `GOWORK=off`。"
        )

    def run_format(self, filepath: str | Path):
        file_or_dir = str(Path(filepath).absolute())
        if shutil.which("gofmt") is None:
            self.logger.warning("[!] gofmt command not found, skip formatting for %s", file_or_dir)
            return ""
        try:
            process = subprocess.run(
                ["gofmt", "-s", "-w", file_or_dir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            self.logger.error("[x] gofmt: %s", exc.stderr.strip())
            return exc.stderr
        return process.stdout.strip()

    def run_go_enum(self, filepath: Union[str, Path], extra_args: Optional[list[str]] = None) -> None:
        executable = shutil.which("go-enum")
        if executable is None:
            self.logger.warning("[!] go-enum command not found, skip enum generation for %s", filepath)
            return

        file_path = Path(filepath).absolute()
        if not file_path.exists():
            self.logger.error("[x] go-enum target missing: %s", file_path)
            return

        args = list(extra_args or self.GO_ENUM_ARGS)
        command = [executable, *args, f"--file={file_path.name}"]
        try:
            subprocess.run(
                command,
                cwd=file_path.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            output = exc.stderr.strip() or exc.stdout.strip()
            self.logger.error("[x] go-enum failed for %s: %s", file_path, output)
