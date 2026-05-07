from __future__ import annotations

import api_blueprint.includes as includes


def test_includes_exports_object_byte_and_null_fields() -> None:
    assert includes.Object.__name__ == "Object"
    assert includes.Byte.__name__ == "Byte"
    assert includes.Null.__name__ == "Null"
