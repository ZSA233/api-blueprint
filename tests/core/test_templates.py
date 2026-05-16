from __future__ import annotations

from api_blueprint.writer.core.templates import _template_lookup_name, _template_relative_parts


def test_template_relative_parts_normalize_cross_platform_separators() -> None:
    assert _template_relative_parts(r"views\_gen_types") == ("views", "_gen_types")
    assert _template_relative_parts("./runtime/nested") == ("runtime", "nested")


def test_template_lookup_name_always_uses_forward_slashes() -> None:
    assert _template_lookup_name(r"views\_gen_types", "types.go.j2") == "views/_gen_types/types.go.j2"
