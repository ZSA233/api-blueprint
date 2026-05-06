from __future__ import annotations

import enum

from api_blueprint.contract import build_contract_graph
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import Array, Enum, Int, Map, String, Model
from api_blueprint.writer.grpc.proto_writer import render_proto_files


def _block(text: str, header: str) -> str:
    start = text.index(header)
    end = text.index("\n}", start) + 2
    return text[start:end]


class OpenRequest(Model):
    run_id = String(description="run id")


class ServerMessage(Model):
    text = String(description="text")


class ClientMessage(Model):
    text = String(description="text")


class Color(enum.StrEnum):
    RED = "red"
    BLUE = "blue"


class NestedPayload(Model):
    count = Int(description="count")


class RichPayload(Model):
    name = String(description="name")
    nested = NestedPayload(description="nested")
    colors = Array[Enum[Color]](description="colors")


class MapArrayPayload(Model):
    items = Map[String, Array[NestedPayload]](description="items")


class ANON_Foo_bar(Model):
    value = String(description="value")


class RefPayload(Model):
    nested = ANON_Foo_bar(description="nested")


def test_grpc_proto_writer_renders_unary_stream_and_bidi_service():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP(message=String(description="message"))
        views.STREAM("/events").OPEN(OpenRequest).SERVER_MESSAGE(ServerMessage)
        views.CHANNEL("/chat").OPEN(OpenRequest).SERVER_MESSAGE(ServerMessage).CLIENT_MESSAGE(ClientMessage)

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="example.api",
        go_package_prefix="example.com/project/grpc/go",
    )

    assert list(files) == ["api/demo.proto"]
    text = files["api/demo.proto"]
    assert 'syntax = "proto3";' in text
    assert "package example.api.demo;" in text
    assert 'option go_package = "example.com/project/grpc/go/api;api";' in text
    assert "service DemoService {" in text
    assert "rpc Ping (PingRequest) returns (PingResponse);" in text
    assert "rpc Events (EventsRequest) returns (stream ServerMessage);" in text
    assert "rpc Chat (stream ClientMessage) returns (stream ServerMessage);" in text


def test_grpc_proto_writer_renders_rpc_request_schema_nested_models_and_enums():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/submit").REQ(RichPayload).RSP(RichPayload)

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="example.api",
        go_package_prefix="example.com/project/grpc/go",
    )

    text = files["api/demo.proto"]
    assert "rpc Submit (SubmitRequest) returns (SubmitResponse);" in text
    request = _block(text, "message SubmitRequest {")
    assert "  string name = 1;" in request
    assert "  NestedPayload nested = 2;" in request
    assert "  repeated Color colors = 3;" in request

    response = _block(text, "message SubmitResponse {")
    assert "  string name = 1;" in response
    assert "  NestedPayload nested = 2;" in response
    assert "  repeated Color colors = 3;" in response

    nested = _block(text, "message NestedPayload {")
    assert "  int64 count = 1;" in nested

    color = _block(text, "enum Color {")
    assert "  COLOR_UNSPECIFIED = 0;" in color
    assert "  COLOR_RED = 1;" in color
    assert "  COLOR_BLUE = 2;" in color


def test_grpc_proto_writer_wraps_repeated_map_values_in_message():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/map-array").RSP(MapArrayPayload)

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="example.api",
        go_package_prefix="example.com/project/grpc/go",
    )

    text = files["api/demo.proto"]
    response = _block(text, "message MapArrayResponse {")
    assert "  map<string, MapArrayResponseItemsValue> items = 1;" in response
    wrapper = _block(text, "message MapArrayResponseItemsValue {")
    assert "  repeated NestedPayload value = 1;" in wrapper


def test_grpc_proto_writer_normalizes_message_declarations_and_references():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/anon").RSP(RefPayload)

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="example.api",
        go_package_prefix="example.com/project/grpc/go",
    )

    text = files["api/demo.proto"]
    response = _block(text, "message AnonResponse {")
    assert "  ANONFooBar nested = 1;" in response
    assert "message ANONFooBar {" in text
    assert "message ANON_Foo_bar {" not in text


def test_grpc_proto_writer_derives_service_packages_to_avoid_cross_file_name_collisions():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/abc").RSP(message=String(description="message"))
    with bp.group("/hello") as views:
        views.GET("/abc").RSP(message=String(description="message"))

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="example.api",
        go_package_prefix="example.com/project/grpc/go",
    )

    assert "package example.api.demo;" in files["api/demo.proto"]
    assert "package example.api.hello;" in files["api/hello.proto"]
