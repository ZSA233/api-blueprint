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
