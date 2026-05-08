from __future__ import annotations

from api_blueprint.engine.utils import join_path_imports


def test_join_path_imports_normalizes_windows_separators() -> None:
    assert (
        join_path_imports(r"example.com\generated", r"golang\providers")
        == "example.com/generated/golang/providers"
    )
