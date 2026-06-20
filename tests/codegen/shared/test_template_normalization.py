from __future__ import annotations

from api_blueprint.writer.core.templates import normalize_generated_source


def test_golang_generated_source_collapses_excess_blank_lines_before_gofmt() -> None:
    source = "package demo\n\n\n\nfunc Ping() {}\n\n\n"

    assert normalize_generated_source("golang", source) == "package demo\n\nfunc Ping() {}\n"


def test_python_generated_source_keeps_existing_blank_line_behavior() -> None:
    source = "class Demo:\n\n\n    pass\n\n"

    assert normalize_generated_source("python", source) == source
