from __future__ import annotations

from scripts import release_assets
from scripts import release_version
from tests.support import REPO_ROOT


def test_release_contract_files_exist():
    release_assets.validate_config(REPO_ROOT)


def test_readme_files_remain_structurally_mirrored():
    release_assets.validate_docs(REPO_ROOT)


def test_release_tag_matches_repository_version_state():
    release_assets.validate_release_version(REPO_ROOT, release_version.check_sync(REPO_ROOT).tag)


def test_makefile_exposes_example_validation_and_release_preflight_uses_it():
    root_text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    text = _makefile_text()

    example_block = _target_block(text, "example-validation")
    compile_block = _target_block(text, "example-compile-check")
    refresh_block = _target_block(text, "example-refresh")
    refresh_go_server_block = _target_block(text, "example-refresh-go-server")
    refresh_go_client_block = _target_block(text, "example-refresh-go-client")
    refresh_typescript_block = _target_block(text, "example-refresh-typescript")
    refresh_python_block = _target_block(text, "example-refresh-python")
    refresh_kotlin_block = _target_block(text, "example-refresh-kotlin")
    refresh_java_block = _target_block(text, "example-refresh-java")
    refresh_flutter_block = _target_block(text, "example-refresh-flutter")
    refresh_swift_block = _target_block(text, "example-refresh-swift")
    refresh_grpc_block = _target_block(text, "example-refresh-grpc")
    refresh_wails_block = _target_block(text, "example-refresh-wails")
    refresh_wails_hello_block = _target_block(text, "example-refresh-wails-hello")
    validation_go_server_block = _target_block(text, "example-validation-go-server")
    validation_go_client_block = _target_block(text, "example-validation-go-client")
    validation_typescript_block = _target_block(text, "example-validation-typescript")
    validation_python_block = _target_block(text, "example-validation-python")
    validation_kotlin_block = _target_block(text, "example-validation-kotlin")
    validation_java_block = _target_block(text, "example-validation-java")
    validation_flutter_block = _target_block(text, "example-validation-flutter")
    validation_swift_block = _target_block(text, "example-validation-swift")
    validation_grpc_block = _target_block(text, "example-validation-grpc")
    validation_wails_block = _target_block(text, "example-validation-wails")
    validation_wails_hello_block = _target_block(text, "example-validation-wails-hello")
    conformance_block = _target_block(text, "example-conformance")
    conformance_list_block = _target_block(text, "example-conformance-list")
    conformance_generate_block = _target_block(text, "example-conformance-generate")
    conformance_run_block = _target_block(text, "example-conformance-run")
    conformance_check_block = _target_block(text, "example-conformance-check")
    conformance_refresh_block = _target_block(text, "example-conformance-refresh")
    golang_suite_block = _target_block(text, "example-golang-suite")
    java_suite_block = _target_block(text, "example-java-suite")
    benchmark_binary_block = _target_block(text, "benchmark-binary")
    test_fast_block = _target_block(text, "test-fast")
    test_toolchain_smoke_block = _target_block(text, "test-toolchain-smoke")
    test_packaging_smoke_block = _target_block(text, "test-packaging-smoke")
    test_ci_block = _target_block(text, "test-ci")
    test_durations_block = _target_block(text, "test-durations")
    preflight_block = _target_block(text, "release-preflight")
    tag_check_block = _target_block(text, "release-tag-check")

    assert ".DEFAULT_GOAL := help" in root_text
    assert "include make/core.mk" in root_text
    assert "include make/examples.mk" in root_text
    assert "include make/wails.mk" in root_text
    assert "include make/release.mk" in root_text
    assert "help:" in text
    assert "make sync" in _target_block(text, "help")
    assert 'EXAMPLE_CONFORMANCE_SERVER ?= go' in text
    assert 'EXAMPLE_CONFORMANCE_CLIENTS ?= go,typescript,kotlin,flutter' in text
    assert 'EXAMPLE_CONFORMANCE_SCENARIOS ?=' in text
    assert 'EXAMPLE_CONFORMANCE_KEEP_WORKSPACE ?= 0' in text
    assert 'EXAMPLE_CONFORMANCE_SWIFT_RUNTIME_PROFILE ?= modern' in text
    assert '--swift-runtime-profile "$(EXAMPLE_CONFORMANCE_SWIFT_RUNTIME_PROFILE)"' in text
    assert 'EXAMPLE_BENCH_SERVERS ?= go' in text
    assert 'EXAMPLE_BENCH_SCENARIOS ?= rpc-json,binary' in text
    assert 'EXAMPLE_BENCH_REQUESTS ?= 1000' in text
    assert 'EXAMPLE_BENCH_CONCURRENCY ?= 16' in text
    assert 'EXAMPLE_BENCH_WARMUP ?= 100' in text
    assert 'SWIFT_RUNTIME_BENCH_SCENARIOS ?= all' in text
    assert 'SWIFT_RUNTIME_BENCH_COUNT ?= 100' in text
    assert 'SWIFT_RUNTIME_BENCH_PAYLOAD_BYTES ?= 262144' in text
    assert "uv run python scripts/example_validation.py" in example_block
    assert "uv run python scripts/example_validation.py --mode compile" in compile_block
    assert "uv run python scripts/example_validation.py --mode refresh" in refresh_block
    assert "uv run python scripts/example_validation.py --mode refresh --target go.server" in refresh_go_server_block
    assert "uv run python scripts/example_validation.py --mode refresh --target go.client" in refresh_go_client_block
    assert "uv run python scripts/example_validation.py --mode refresh --target typescript.client" in refresh_typescript_block
    assert "uv run python scripts/example_validation.py --mode refresh --target python.http" in refresh_python_block
    assert "uv run python scripts/example_validation.py --mode refresh --target kotlin.http" in refresh_kotlin_block
    assert "uv run python scripts/example_validation.py --mode refresh --target java.http" in refresh_java_block
    assert "uv run python scripts/example_validation.py --mode refresh --target flutter.client" in refresh_flutter_block
    assert "uv run python scripts/example_validation.py --mode refresh --target swift.client" in refresh_swift_block
    assert "uv run python scripts/example_validation.py --mode refresh --target grpc" in refresh_grpc_block
    assert "uv run python scripts/example_validation.py --mode refresh --target wails.blueprint" in refresh_wails_block
    assert "uv run python scripts/example_validation.py --mode refresh --target wails.hello" in refresh_wails_hello_block
    assert "uv run python scripts/example_validation.py --target go.server" in validation_go_server_block
    assert "uv run python scripts/example_validation.py --target go.client" in validation_go_client_block
    assert "uv run python scripts/example_validation.py --target typescript.client" in validation_typescript_block
    assert "uv run python scripts/example_validation.py --target python.http" in validation_python_block
    assert "uv run python scripts/example_validation.py --target kotlin.http" in validation_kotlin_block
    assert "uv run python scripts/example_validation.py --target java.http" in validation_java_block
    assert "uv run python scripts/example_validation.py --target flutter.client" in validation_flutter_block
    assert "uv run python scripts/example_validation.py --target swift.client" in validation_swift_block
    assert "uv run python scripts/example_validation.py --target grpc" in validation_grpc_block
    assert "uv run python scripts/example_validation.py --target wails.blueprint" in validation_wails_block
    assert "uv run python scripts/example_validation.py --target wails.hello" in validation_wails_hello_block
    assert "$(MAKE) example-conformance-check" in conformance_block
    assert "uv run python -m scripts.example_conformance list" in conformance_list_block
    assert "uv run python -m scripts.example_conformance generate" in conformance_generate_block
    assert "$(EXAMPLE_CONFORMANCE_KEEP_ARG)" in conformance_generate_block
    assert "uv run python -m scripts.example_conformance run $(EXAMPLE_CONFORMANCE_MATRIX_ARGS)" in conformance_run_block
    assert "$(EXAMPLE_CONFORMANCE_KEEP_ARG)" in conformance_run_block
    assert "uv run python -m scripts.example_conformance check $(EXAMPLE_CONFORMANCE_MATRIX_ARGS)" in conformance_check_block
    assert "uv run python -m scripts.example_conformance refresh $(EXAMPLE_CONFORMANCE_MATRIX_ARGS)" in conformance_refresh_block
    assert "uv run python scripts/example_validation.py --scope blueprint --mode golang-suite" in golang_suite_block
    assert "uv run python scripts/example_validation.py --scope blueprint --mode java-suite" in java_suite_block
    benchmark_list_block = _target_block(text, "benchmark-list")
    benchmark_swift_runtime_block = _target_block(text, "benchmark-swift-runtime")
    benchmark_protocol_block = _target_block(text, "example-benchmark-protocol")
    benchmark_suite_block = _target_block(text, "example-benchmark")
    assert "uv run python -m scripts.example_benchmark list" in benchmark_list_block
    assert 'uv run python scripts/benchmark_binary.py --target "$(BINARY_BENCH_TARGET)" --count "$(BINARY_BENCH_COUNT)"' in benchmark_binary_block
    assert "uv run python -m scripts.example_benchmark swift-runtime" in benchmark_swift_runtime_block
    assert '--scenario "$(SWIFT_RUNTIME_BENCH_SCENARIOS)"' in benchmark_swift_runtime_block
    assert '--count "$(SWIFT_RUNTIME_BENCH_COUNT)"' in benchmark_swift_runtime_block
    assert '--payload-bytes "$(SWIFT_RUNTIME_BENCH_PAYLOAD_BYTES)"' in benchmark_swift_runtime_block
    assert "uv run python -m scripts.example_benchmark protocol" in benchmark_protocol_block
    assert '--servers "$(EXAMPLE_BENCH_SERVERS)"' in benchmark_protocol_block
    assert '--scenario "$(EXAMPLE_BENCH_SCENARIOS)"' in benchmark_protocol_block
    assert '--requests "$(EXAMPLE_BENCH_REQUESTS)"' in benchmark_protocol_block
    assert '--concurrency "$(EXAMPLE_BENCH_CONCURRENCY)"' in benchmark_protocol_block
    assert '--warmup "$(EXAMPLE_BENCH_WARMUP)"' in benchmark_protocol_block
    assert "$(MAKE) benchmark-binary" in benchmark_suite_block
    assert "$(MAKE) example-benchmark-protocol" in benchmark_suite_block
    assert (
        'uv run pytest -q -n auto -m "not example_validation and not toolchain_smoke and not packaging_smoke"'
        in test_fast_block
    )
    assert 'uv run pytest -q -m "toolchain_smoke"' in test_toolchain_smoke_block
    assert 'uv run pytest -q -m "packaging_smoke"' in test_packaging_smoke_block
    assert "$(MAKE) test-fast" in test_ci_block
    assert "$(MAKE) test-toolchain-smoke" in test_ci_block
    assert "$(MAKE) test-packaging-smoke" in test_ci_block
    assert 'uv run pytest -q -m "not example_validation" --durations=40' in test_durations_block
    assert "$(MAKE) example-validation" in preflight_block
    assert 'uv run python scripts/release_version.py check-sync --tag "$(RELEASE_TAG)"' in tag_check_block
    assert "uv run python scripts/release_assets.py validate-config" in tag_check_block
    assert "uv run python scripts/release_assets.py validate-docs" in tag_check_block
    assert 'uv run python scripts/release_assets.py validate-release-version --tag "$(RELEASE_TAG)"' in tag_check_block


def test_ci_and_release_bundle_share_example_toolchain_setup():
    ci_text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    release_text = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    release_rc_text = (REPO_ROOT / ".github" / "workflows" / "release-rc.yml").read_text(encoding="utf-8")
    release_bundle_text = (
        REPO_ROOT / ".github" / "actions" / "release-bundle" / "action.yml"
    ).read_text(encoding="utf-8")
    toolchain_text = (
        REPO_ROOT / ".github" / "actions" / "setup-example-toolchains" / "action.yml"
    ).read_text(encoding="utf-8")
    example_validation_job = _job_block(ci_text, "example-validation")
    python_tests_job = _job_block(ci_text, "python-tests")
    python_toolchain_smoke_job = _job_block(ci_text, "python-toolchain-smoke")
    python_packaging_smoke_job = _job_block(ci_text, "python-packaging-smoke")

    assert "example-validation:" in ci_text
    assert "./.github/actions/setup-example-toolchains" in ci_text
    assert "workflow_dispatch" in example_validation_job
    assert "refs/heads/release/" in example_validation_job
    assert "matrix:" in example_validation_job
    assert "target: go.server" in example_validation_job
    assert "target: python.http" in example_validation_job
    assert "target: wails.hello" in example_validation_job
    assert 'uv run python scripts/example_validation.py --target "${{ matrix.target }}"' in example_validation_job
    assert "example-validation" not in python_tests_job
    assert "release-contract" in python_tests_job
    assert "actions/setup-go@v6" not in python_tests_job
    assert "Build package" not in python_tests_job
    assert (
        'uv run pytest -q -n auto -m "not example_validation and not toolchain_smoke and not packaging_smoke"'
        in python_tests_job
    )
    assert "python-toolchain-smoke:" in ci_text
    assert "python-packaging-smoke:" in ci_text
    assert "./.github/actions/setup-example-toolchains" in python_toolchain_smoke_job
    assert "go: true" in python_toolchain_smoke_job
    assert "go_enum: true" in python_toolchain_smoke_job
    assert "node: true" in python_toolchain_smoke_job
    assert "typescript: true" in python_toolchain_smoke_job
    assert 'uv run pytest -q -m "toolchain_smoke"' in python_toolchain_smoke_job
    assert "./.github/actions/setup-example-toolchains" not in python_packaging_smoke_job
    assert 'uv run pytest -q -m "packaging_smoke"' in python_packaging_smoke_job
    assert "./.github/actions/setup-example-toolchains" in release_bundle_text
    assert 'run: make release-tag-check RELEASE_TAG="${{ inputs.release_tag }}"' in release_bundle_text
    assert "make release-preflight" not in release_bundle_text
    assert "actions/setup-java@v5" in toolchain_text
    assert "inputs:" in toolchain_text
    assert "inputs.java == 'true'" in toolchain_text
    assert 'java-version: "17"' in toolchain_text
    assert "actions/setup-go@v6" in toolchain_text
    assert "actions/setup-node@v6" in toolchain_text
    assert 'node-version: "24"' in toolchain_text
    assert "examples/golang/server/go.sum" in toolchain_text
    assert "examples/golang/client/go.sum" in toolchain_text
    assert "examples/grpc/go/go.sum" in toolchain_text
    assert "protobuf-compiler" not in toolchain_text
    assert toolchain_text.count("apt-get update") == 1
    assert "github.com/abice/go-enum@v0.9.2" in toolchain_text
    assert "google.golang.org/protobuf/cmd/protoc-gen-go@v1.36.10" in toolchain_text
    assert "google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.6.0" in toolchain_text
    assert "GITHUB_PATH" in toolchain_text
    assert "python-tests:" in ci_text
    assert "build:\n    runs-on: ubuntu-22.04" in release_text
    assert "build:\n    runs-on: ubuntu-22.04" in release_rc_text


def test_readme_stays_as_onboarding_entrypoint():
    readme_zh = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_en = (REPO_ROOT / "README_EN.md").read_text(encoding="utf-8")

    assert "## 生成产物与用户文件" not in readme_zh
    assert "## Generated Artifacts And User Files" not in readme_en
    assert "## 30 秒示例" in readme_zh
    assert "## 30-Second Example" in readme_en
    assert "[docs/zh/binary-schema.md]" in readme_zh
    assert "[docs/en/binary-schema.md]" in readme_en


def _target_block(text: str, target: str) -> str:
    marker = f"{target}:"
    lines = text.splitlines()
    collecting = False
    collected: list[str] = []
    for line in lines:
        if not collecting and line.startswith(marker):
            collecting = True
            collected.append(line)
            continue
        if collecting:
            if line and not line.startswith("\t") and not line.startswith(" "):
                break
            collected.append(line)

    if not collected:
        raise AssertionError(f"target {target!r} not found in Makefile")
    return "\n".join(collected)


def _makefile_text() -> str:
    chunks = [(REPO_ROOT / "Makefile").read_text(encoding="utf-8")]
    chunks.extend(path.read_text(encoding="utf-8") for path in sorted((REPO_ROOT / "make").glob("*.mk")))
    return "\n".join(chunks)


def _job_block(text: str, job: str) -> str:
    marker = f"  {job}:"
    lines = text.splitlines()
    collecting = False
    collected: list[str] = []
    for line in lines:
        if not collecting and line == marker:
            collecting = True
            collected.append(line)
            continue
        if collecting:
            if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
                break
            collected.append(line)

    if not collected:
        raise AssertionError(f"job {job!r} not found in workflow")
    return "\n".join(collected)
