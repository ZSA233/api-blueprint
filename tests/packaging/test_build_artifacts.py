from __future__ import annotations

import shutil
import subprocess

from scripts import release_assets
from scripts import release_version
from tests.support import REPO_ROOT


def test_built_artifacts_include_runtime_assets_and_install_cleanly(tmp_path):
    uv = shutil.which("uv")
    assert uv is not None

    dist_dir = tmp_path / "dist"
    subprocess.run(
        [uv, "build", "--sdist", "--wheel", "--out-dir", str(dist_dir)],
        cwd=REPO_ROOT,
        check=True,
    )

    artifacts = release_assets.validate_dist_artifacts(dist_dir)
    assert len(artifacts.wheels) == 1
    assert len(artifacts.sdists) == 1

    release_assets.install_check(REPO_ROOT, dist_dir, release_version.check_sync(REPO_ROOT).tag)
