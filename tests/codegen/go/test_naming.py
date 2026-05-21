from __future__ import annotations

from api_blueprint.writer.core.go_naming import to_go_exported_name, to_go_package_name, to_go_package_path


def test_go_package_name_normalizes_invalid_route_segments() -> None:
    assert to_go_package_name("/api-v1") == "api_v1"
    assert to_go_package_name("///") == "root"
    assert to_go_package_name("/1api") == "p_1api"
    assert to_go_package_name("/package") == "package_pkg"
    assert to_go_package_name("/api---v1") == "api_v1"


def test_go_package_path_collapses_route_paths_to_one_package_segment() -> None:
    assert to_go_package_path("/admin/v1") == "admin_v1"
    assert to_go_package_path("/admin//v1/") == "admin_v1"
    assert to_go_package_path("", fallback="api") == "api"


def test_go_exported_name_uses_go_identifier_shape() -> None:
    assert to_go_exported_name("admin_v1") == "AdminV1"
    assert to_go_exported_name("1api") == "Value1api"
    assert to_go_exported_name("") == "Value"
