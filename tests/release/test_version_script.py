from __future__ import annotations

from pathlib import Path

from api_blueprint import __version__
from api_blueprint.release_version import (
    ReleaseVersionConfig,
    load_release_version_config,
    parse_python_release_version,
    parse_release_tag,
    read_python_version_file,
)
from scripts import release_version
from tests.support import REPO_ROOT


def _init_temp_repo(repo_root: Path) -> None:
    (repo_root / "src" / "api_blueprint").mkdir(parents=True, exist_ok=True)
    (repo_root / "release-version.toml").write_text(
        'base_version = "1.2.3"\nchannel = "stable"\n',
        encoding="utf-8",
    )
    (repo_root / "src" / "api_blueprint" / "_version.py").write_text(
        '__version__ = "1.2.3"\n',
        encoding="utf-8",
    )


def test_release_version_parsers_support_stable_and_rc_values():
    assert parse_python_release_version("1.2.3").tag == "v1.2.3"
    assert parse_python_release_version("1.2.3rc4").tag == "v1.2.3-rc.4"
    assert parse_release_tag("v2.0.0").python_version == "2.0.0"
    assert parse_release_tag("v2.0.0-rc.2").python_version == "2.0.0rc2"


def test_set_release_version_updates_temp_repo_and_keeps_files_in_sync(tmp_path):
    repo_root = tmp_path / "repo"
    _init_temp_repo(repo_root)

    rc_config = ReleaseVersionConfig(base_version="1.2.4", channel="rc", rc_number=2)
    rc_release = release_version.set_release_version(repo_root, rc_config, check=True)
    assert rc_release.tag == "v1.2.4-rc.2"
    assert load_release_version_config(repo_root / "release-version.toml") == rc_config
    assert read_python_version_file(repo_root / "src" / "api_blueprint" / "_version.py") == "1.2.4rc2"

    stable_config = ReleaseVersionConfig(base_version="1.2.4", channel="stable")
    stable_release = release_version.set_release_version(repo_root, stable_config, check=True)
    assert stable_release.tag == "v1.2.4"
    assert read_python_version_file(repo_root / "src" / "api_blueprint" / "_version.py") == "1.2.4"


def test_repository_release_files_are_currently_in_sync():
    release = release_version.check_sync(REPO_ROOT)
    assert release.python_version == __version__
