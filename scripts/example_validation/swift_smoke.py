from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from api_blueprint.application import generator

from .models import ExampleValidationError

SWIFT_IOS_SMOKE_ENV = "API_BLUEPRINT_SWIFT_IOS_SMOKE"
SWIFT_RUNTIME_PROFILES = ("modern", "ios14-compat")


def validate_swift_runtime_profile(runtime_profile: str) -> str:
    if runtime_profile not in SWIFT_RUNTIME_PROFILES:
        raise ValueError(
            "swift runtime profile must be one of: " + ", ".join(SWIFT_RUNTIME_PROFILES)
        )
    return runtime_profile


def write_swift_client_config_override(
    source_config: Path,
    output_config: Path,
    *,
    runtime_profile: str,
    out_dir: Path | str | None = None,
) -> None:
    runtime_profile = validate_swift_runtime_profile(runtime_profile)
    lines = source_config.read_text(encoding="utf-8").splitlines()
    rendered: list[str] = []
    in_swift_block = False
    saw_swift_block = False
    saw_runtime_profile = False
    saw_out_dir = False

    def emit_missing_fields() -> None:
        nonlocal saw_runtime_profile, saw_out_dir
        if not saw_runtime_profile:
            rendered.append(f"runtime_profile = {_toml_string(runtime_profile)}")
        if out_dir is not None and not saw_out_dir:
            rendered.append(f"out_dir = {_toml_string(str(out_dir))}")
        saw_runtime_profile = False
        saw_out_dir = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[[") and stripped.endswith("]]"):
            if in_swift_block:
                emit_missing_fields()
            in_swift_block = stripped == "[[swift.client]]"
            saw_swift_block = saw_swift_block or in_swift_block
            rendered.append(line)
            continue
        if in_swift_block:
            key = stripped.split("=", 1)[0].strip() if "=" in stripped else ""
            if key == "runtime_profile":
                rendered.append(f"runtime_profile = {_toml_string(runtime_profile)}")
                saw_runtime_profile = True
                continue
            if key == "out_dir" and out_dir is not None:
                rendered.append(f"out_dir = {_toml_string(str(out_dir))}")
                saw_out_dir = True
                continue
        rendered.append(line)

    if in_swift_block:
        emit_missing_fields()
    if not saw_swift_block:
        raise ExampleValidationError(f"missing [[swift.client]] table in {source_config}")
    output_config.write_text("\n".join(rendered) + "\n", encoding="utf-8")


def validate_swift_compat_package(workspace_root: Path, swift_bin: str) -> None:
    config_path = workspace_root / "api-blueprint.toml"
    if not config_path.is_file():
        raise ExampleValidationError(f"missing example config for Swift compat smoke: {config_path}")

    temp_config = workspace_root / ".api-blueprint-swift-ios14-compat.toml"
    with tempfile.TemporaryDirectory(prefix="api-blueprint-swift-ios14-compat-") as temp_dir:
        out_dir = Path(temp_dir) / "swift"
        try:
            write_swift_client_config_override(
                config_path,
                temp_config,
                runtime_profile="ios14-compat",
                out_dir=out_dir,
            )
            generator.generate(temp_config, target_ids=("swift.client",))
            _assert_compat_package_shape(out_dir)
            subprocess.run([swift_bin, "build"], cwd=out_dir, check=True)
        finally:
            temp_config.unlink(missing_ok=True)


def validate_swift_ios_simulator_smoke(swift_dir: Path) -> None:
    if os.environ.get(SWIFT_IOS_SMOKE_ENV) != "1":
        return
    xcodebuild = shutil.which("xcodebuild")
    if xcodebuild is None:
        raise ExampleValidationError(
            f"{SWIFT_IOS_SMOKE_ENV}=1 requires Xcode command line tools with `xcodebuild`."
        )
    scheme = _first_swiftpm_library_product(swift_dir / "Package.swift")
    with tempfile.TemporaryDirectory(prefix="api-blueprint-swift-ios-derived-") as temp_dir:
        subprocess.run(
            [
                xcodebuild,
                "-package-path",
                str(swift_dir),
                "-scheme",
                scheme,
                "-destination",
                "generic/platform=iOS Simulator",
                "-derivedDataPath",
                str(Path(temp_dir) / "DerivedData"),
                "build",
            ],
            check=True,
        )


def _assert_compat_package_shape(swift_dir: Path) -> None:
    package_manifest = (swift_dir / "Package.swift").read_text(encoding="utf-8")
    transport = (
        swift_dir
        / "Sources"
        / "ABClientRuntime"
        / "Transports"
        / "HTTP"
        / "GenURLSessionAPITransport.swift"
    ).read_text(encoding="utf-8")
    if ".iOS(.v14)" not in package_manifest:
        raise ExampleValidationError("Swift ios14-compat smoke did not generate an iOS 14 package")
    if ".data(for:" in transport or ".bytes(for:" in transport:
        raise ExampleValidationError("Swift ios14-compat transport uses iOS 15-only URLSession APIs")
    if "APIHTTPCompatByteStreamTask" not in transport:
        raise ExampleValidationError("Swift ios14-compat transport is missing delegate byte-stream support")


def _first_swiftpm_library_product(package_manifest: Path) -> str:
    text = package_manifest.read_text(encoding="utf-8")
    for line in text.splitlines():
        marker = '.library(name: "'
        if marker not in line:
            continue
        start = line.index(marker) + len(marker)
        end = line.find('"', start)
        if end > start:
            return line[start:end]
    raise ExampleValidationError(f"Swift package has no library product: {package_manifest}")


def _toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
