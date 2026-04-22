from __future__ import annotations

from api_blueprint.writer.core.files import ensure_filepath_open


def test_ensure_filepath_open_defaults_to_utf8_for_text_mode(tmp_path):
    target = tmp_path / "nested" / "sample.txt"

    with ensure_filepath_open(target, "w", overwrite=True) as handle:
        assert handle is not None
        handle.write("中文 UTF-8 output")

    assert target.read_text(encoding="utf-8") == "中文 UTF-8 output"
