from __future__ import annotations

from pathlib import Path

from api_blueprint.contract import build_contract_graph
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import Model, String
from api_blueprint.writer.flutter import FlutterWriter
from api_blueprint.writer.golang import GolangClientWriter, GolangWriter
from api_blueprint.writer.grpc import render_proto_files
from api_blueprint.writer.java import JavaClientWriter, JavaServerWriter
from api_blueprint.writer.kotlin import KotlinServerWriter, KotlinWriter
from api_blueprint.writer.python import PythonClientWriter, PythonServerWriter
from api_blueprint.writer.swift import SwiftWriter
from api_blueprint.writer.typescript.writer import TypeScriptWriter


class RoomEvent(Model):
    message = String(description="message")


def _rootless_blueprint() -> Blueprint:
    bp = Blueprint(name="legacy", root="")
    with bp.group("/account") as views:
        views.GET("/profile").RSP(message=String(description="message"))
    with bp.group("/room") as views:
        views.STREAM("/events").SERVER_MESSAGE(RoomEvent)
    bp.is_built = True
    return bp


def _rootless_rpc_blueprint() -> Blueprint:
    bp = Blueprint(name="legacy", root="")
    with bp.group("/account") as views:
        views.GET("/profile").RSP(message=String(description="message"))
    bp.is_built = True
    return bp


def test_rootless_codegen_uses_logical_name_without_changing_urls(tmp_path: Path) -> None:
    bp = _rootless_blueprint()
    graph = build_contract_graph([bp])
    manifest = graph.to_manifest()

    assert [route["id"] for route in manifest["routes"]] == [
        "legacy.account.get.profile",
        "legacy.room.stream.events",
    ]
    assert [route["url"] for route in manifest["routes"]] == [
        "/account/profile",
        "/room/events",
    ]

    go_mod = tmp_path / "go.mod"
    go_mod.write_text("module example.com/generated\n\ngo 1.23.8\n", encoding="utf-8")

    go_server_dir = tmp_path / "go_server"
    go_server_dir.mkdir()
    go_server = GolangWriter(go_server_dir, contract_graph=graph)
    go_server.register(bp)
    go_server.gen()
    assert (go_server_dir / "routes" / "legacy" / "account" / "gen_interface.go").is_file()
    go_stream_http = (
        go_server_dir / "transports" / "http" / "legacy" / "room" / "gen_interface.go"
    ).read_text(encoding="utf-8")
    assert '"/room/events"' in go_stream_http

    go_client_dir = tmp_path / "go_client"
    go_client = GolangClientWriter(
        go_client_dir,
        module="example.com/generated/go_client",
        contract_graph=graph,
    )
    go_client.register(bp)
    go_client.gen()
    assert (go_client_dir / "routes" / "legacy" / "account" / "gen_client.go").is_file()
    go_stream_client = (
        go_client_dir / "routes" / "legacy" / "room" / "gen_client.go"
    ).read_text(encoding="utf-8")
    assert '"/room/events"' in go_stream_client
    assert '"legacy.room.stream.events"' in go_stream_client

    ts_dir = tmp_path / "typescript"
    ts = TypeScriptWriter(ts_dir, contract_graph=graph)
    ts.register(bp)
    ts.gen()
    assert (ts_dir / "legacy" / "routes" / "legacy" / "account" / "gen_client.ts").is_file()
    assert 'path: "/room/events"' in (
        ts_dir / "legacy" / "routes" / "legacy" / "room" / "gen_client.ts"
    ).read_text(encoding="utf-8")

    py_client_dir = tmp_path / "python_client"
    py_client = PythonClientWriter(py_client_dir, contract_graph=graph)
    py_client.register(bp)
    py_client.gen()
    assert (
        py_client_dir / "api_blueprint_generated" / "legacy" / "routes" / "legacy" / "account" / "gen_client.py"
    ).is_file()

    py_server_dir = tmp_path / "python_server"
    py_server = PythonServerWriter(py_server_dir, contract_graph=graph)
    py_server.register(bp)
    py_server.gen()
    assert (
        py_server_dir / "api_blueprint_generated" / "legacy" / "routes" / "legacy" / "account" / "gen_service.py"
    ).is_file()

    kotlin_client_dir = tmp_path / "kotlin_client"
    kotlin_client = KotlinWriter(kotlin_client_dir, package="com.example.generated", contract_graph=graph)
    kotlin_client.register(bp)
    kotlin_client.gen()
    assert (
        kotlin_client_dir
        / "com"
        / "example"
        / "generated"
        / "legacy"
        / "routes"
        / "legacy"
        / "account"
        / "GenAccountApi.kt"
    ).is_file()

    kotlin_server_dir = tmp_path / "kotlin_server"
    kotlin_server = KotlinServerWriter(kotlin_server_dir, package="com.example.generated", contract_graph=graph)
    kotlin_server.register(bp)
    kotlin_server.gen()
    assert (
        kotlin_server_dir
        / "com"
        / "example"
        / "generated"
        / "legacy"
        / "routes"
        / "legacy"
        / "account"
        / "GenAccountService.kt"
    ).is_file()

    java_client_dir = tmp_path / "java_client"
    java_client = JavaClientWriter(java_client_dir, package="com.example.generated", contract_graph=graph)
    java_client.register(bp)
    java_client.gen()
    assert (
        java_client_dir
        / "com"
        / "example"
        / "generated"
        / "legacy"
        / "routes"
        / "legacy"
        / "account"
        / "GenAccountApi.java"
    ).is_file()

    java_server_bp = _rootless_rpc_blueprint()
    java_server_graph = build_contract_graph([java_server_bp])
    java_server_dir = tmp_path / "java_server"
    java_server = JavaServerWriter(
        java_server_dir,
        package="com.example.generated",
        contract_graph=java_server_graph,
        spring_public_paths=["/legacy/**"],
    )
    java_server.register(java_server_bp)
    java_server.gen()
    assert (
        java_server_dir
        / "com"
        / "example"
        / "generated"
        / "legacy"
        / "routes"
        / "legacy"
        / "account"
        / "controllers"
        / "GenAccountController.java"
    ).is_file()
    assert (
        java_server_dir
        / "com"
        / "example"
        / "generated"
        / "legacy"
        / "routes"
        / "legacy"
        / "account"
        / "delegates"
        / "GenAccountDelegate.java"
    ).is_file()
    assert (
        java_server_dir / "com" / "example" / "generated" / "legacy" / "spring" / "GenSpringMvcContractAssertions.java"
    ).is_file()

    flutter_dir = tmp_path / "flutter"
    flutter = FlutterWriter(flutter_dir, package="api_blueprint_example", contract_graph=graph)
    flutter.register(bp)
    flutter.gen()
    assert (
        flutter_dir
        / "lib"
        / "src"
        / "legacy"
        / "routes"
        / "legacy"
        / "account"
        / "gen_account_api.dart"
    ).is_file()

    swift_dir = tmp_path / "swift"
    swift = SwiftWriter(swift_dir, package="ApiBlueprintExampleClient", module="ABClient", contract_graph=graph)
    swift.register(bp)
    swift.gen()
    assert (
        swift_dir
        / "Sources"
        / "ABClientLegacyRoutes"
        / "Legacy"
        / "Routes"
        / "Legacy"
        / "Account"
        / "GenAccountAPI.swift"
    ).is_file()

    protos = render_proto_files(
        graph,
        package="api_blueprint.example",
        go_package_prefix="example.com/generated/pb",
    )
    assert set(protos) == {"legacy/account.proto", "legacy/room.proto"}
    assert "package api_blueprint.example.legacy.account;" in protos["legacy/account.proto"]
