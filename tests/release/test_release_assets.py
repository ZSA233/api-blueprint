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
    preflight_block = _target_block(text, "release-preflight")

    assert "uv run python scripts/example_validation.py" in example_block
    assert "uv run python scripts/example_validation.py --mode compile" in compile_block
    assert "uv run python scripts/example_validation.py --mode refresh" in refresh_block
    assert "$(MAKE) example-validation" in preflight_block


def test_ci_workflow_keeps_example_validation_as_a_separate_job():
    text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "example-validation:" in text
    assert "protobuf-compiler" in text
    assert "protoc-gen-go@v1.36.10" in text
    assert "protoc-gen-go-grpc@v1.6.0" in text
    assert "GITHUB_PATH" in text
    assert 'uv run pytest -q -m "not example_validation"' in text


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
