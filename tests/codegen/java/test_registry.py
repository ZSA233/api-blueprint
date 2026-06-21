from __future__ import annotations

from .helpers import *


def test_java_name_helpers_preserve_expected_output() -> None:
    assert to_java_type_name("/api/demo/1put") == "ApiDemo1put"
    assert to_java_member_name("delete$") == "delete"
    assert to_java_member_name("class") == "classValue"
    assert to_java_package_path("/static") == "static_"

def test_java_model_catalog_builds_record_fields_and_enum_metadata() -> None:
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/submit").REQ(Payload).RSP(Result)

    manifest = build_contract_graph([bp]).to_manifest()
    catalog = JavaModelCatalog(manifest["schemas"])
    schema = catalog.schema("Payload", owner_group=None)
    enum_type = catalog.enums()[0]

    assert schema.name == "Payload"
    assert [field.java_name for field in schema.fields] == ["userId", "scores", "kind"]
    assert [field.wire_name for field in schema.fields] == ["user_id", "scores", "kind"]
    assert [field.java_type for field in schema.fields] == ["String", "List<Long>", "GenApiTypes.WireEnum"]
    assert enum_type.name == "WireEnum"
    assert [member.java_name for member in enum_type.values] == ["FIRST", "SECOND"]
    assert [member.literal for member in enum_type.values] == ['"first"', '"second"']
    assert [member.comment for member in enum_type.values] == ["First option", "Second option"]
