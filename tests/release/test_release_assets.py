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
    text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    example_block = _target_block(text, "example-validation")
    compile_block = _target_block(text, "example-compile-check")
    refresh_block = _target_block(text, "example-refresh")
    golang_suite_block = _target_block(text, "example-golang-suite")
    java_suite_block = _target_block(text, "example-java-suite")
    preflight_block = _target_block(text, "release-preflight")
    tag_check_block = _target_block(text, "release-tag-check")

    assert "uv run python scripts/example_validation.py" in example_block
    assert "uv run python scripts/example_validation.py --mode compile" in compile_block
    assert "uv run python scripts/example_validation.py --mode refresh" in refresh_block
    assert "uv run python scripts/example_validation.py --scope blueprint --mode golang-suite" in golang_suite_block
    assert "uv run python scripts/example_validation.py --scope blueprint --mode java-suite" in java_suite_block
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

    assert "example-validation:" in ci_text
    assert "./.github/actions/setup-example-toolchains" in ci_text
    assert "workflow_dispatch" in example_validation_job
    assert "refs/heads/release/" in example_validation_job
    assert "example-validation" not in python_tests_job
    assert "release-contract" in python_tests_job
    assert "./.github/actions/setup-example-toolchains" in release_bundle_text
    assert 'run: make release-tag-check RELEASE_TAG="${{ inputs.release_tag }}"' in release_bundle_text
    assert "make release-preflight" not in release_bundle_text
    assert "actions/setup-java@v5" in toolchain_text
    assert 'java-version: "17"' in toolchain_text
    assert "actions/setup-go@v6" in toolchain_text
    assert "actions/setup-node@v6" in toolchain_text
    assert 'node-version: "24"' in toolchain_text
    assert "examples/golang/server/go.sum" in toolchain_text
    assert "protobuf-compiler" not in toolchain_text
    assert toolchain_text.count("apt-get update") == 1
    assert "github.com/abice/go-enum@v0.9.2" in toolchain_text
    assert "google.golang.org/protobuf/cmd/protoc-gen-go@v1.36.10" in toolchain_text
    assert "google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.6.0" in toolchain_text
    assert "GITHUB_PATH" in toolchain_text
    assert 'uv run pytest -q -m "not example_validation"' in ci_text
    assert "python-tests:" in ci_text
    assert "actions/setup-go@v6" in ci_text
    assert 'go-version: "1.25"' in ci_text
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
