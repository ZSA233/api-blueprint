from __future__ import annotations

from .helpers import *


def test_flutter_name_helpers_preserve_expected_output() -> None:
    assert to_dart_type_name("/api/demo/1put") == "ApiDemo1put"
    assert to_dart_identifier("delete$") == "delete"
    assert to_dart_identifier("class") == "class_"
