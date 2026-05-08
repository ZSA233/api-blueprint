from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, Generator, Mapping, Sequence

from api_blueprint.contract import ContractGraph, build_contract_graph
from api_blueprint.route_selection import normalize_selection_rules
from api_blueprint.writer.core.base import BaseBlueprint, BaseWriter
from api_blueprint.writer.core.files import ensure_filepath_open
from api_blueprint.writer.core.planning import route_matches_rule


logger = logging.getLogger("GolangClientWriter")
logger.setLevel(logging.INFO)


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class GoClientRoute:
    route: JsonObject

    @property
    def operation(self) -> str:
        return _go_exported(str(self.route.get("operation") or "Call"))

    @property
    def method(self) -> str:
        methods = self.route.get("methods")
        if isinstance(methods, list) and methods:
            return str(methods[0]).upper()
        return "GET"

    @property
    def url(self) -> str:
        return str(self.route.get("url") or "")

    @property
    def route_id(self) -> str:
        return str(self.route.get("id") or "")

    @property
    def kind(self) -> str:
        return str(self.route.get("kind") or "rpc")

    @property
    def request(self) -> Mapping[str, Any]:
        request = self.route.get("request")
        return request if isinstance(request, Mapping) else {}

    @property
    def response(self) -> Mapping[str, Any]:
        response = self.route.get("response")
        return response if isinstance(response, Mapping) else {}

    @property
    def connection(self) -> Mapping[str, Any]:
        connection = self.route.get("connection")
        return connection if isinstance(connection, Mapping) else {}


@dataclass
class GoClientGroup:
    segments: tuple[str, ...]
    package: str
    client_class: str
    routes: list[GoClientRoute] = field(default_factory=list)


class GolangClientBlueprint(BaseBlueprint["GolangClientWriter"]):
    pass


class GolangClientWriter(BaseWriter[GolangClientBlueprint]):
    def __init__(
        self,
        working_dir: str | Path = ".",
        *,
        module: str | None = None,
        base_url: str | None = None,
        base_url_expr: str | None = None,
        include: Sequence[str] = (),
        exclude: Sequence[str] = (),
        contract_graph: ContractGraph | None = None,
    ) -> None:
        super().__init__(working_dir)
        self.module = module or ""
        self.base_url = base_url or ""
        self.base_url_expr = base_url_expr
        self.include = normalize_selection_rules(include)
        self.exclude = normalize_selection_rules(exclude)
        self.contract_graph = contract_graph
        self._written_files: set[Path] = set()

    def gen(self) -> None:
        graph = self.contract_graph or build_contract_graph([bp.bp for bp in self.bps])
        manifest = graph.to_manifest()
        routes = [dict(route) for route in _list_of_maps(manifest.get("routes")) if self._route_selected(route)]
        schemas = _mapping_of_maps(manifest.get("schemas"))
        services = _mapping_of_maps_by_id(manifest.get("services"))
        type_names = _TypeNames(schemas)
        groups = _build_groups(routes, services)

        self._write_runtime_files(schemas, type_names)
        for group in groups:
            self._write_group_files(group, schemas, type_names)
        self._write_http_files()
        self._format_written_files()

    def _route_selected(self, route: Mapping[str, Any]) -> bool:
        if self.include and not any(route_matches_rule(route, rule) for rule in self.include):
            return False
        return not any(route_matches_rule(route, rule) for rule in self.exclude)

    def _write_runtime_files(self, schemas: Mapping[str, JsonObject], type_names: "_TypeNames") -> None:
        self._write_generated("runtime/gen_client.go", _runtime_client_source())
        self._write_generated("runtime/gen_errors.go", _runtime_errors_source())
        self._write_generated("runtime/gen_models.go", _runtime_models_source(schemas, type_names))

    def _write_group_files(
        self,
        group: GoClientGroup,
        schemas: Mapping[str, JsonObject],
        type_names: "_TypeNames",
    ) -> None:
        route_dir = Path("routes").joinpath(*group.segments)
        self._write_generated(route_dir / "gen_models.go", _group_models_source(group, schemas, type_names, self.runtime_import))
        self._write_generated(route_dir / "gen_client.go", _group_client_source(group, type_names, self.runtime_import))
        self._write_user_file(route_dir / "client.go", _group_public_source(group))

    def _write_http_files(self) -> None:
        self._write_generated("transports/http/gen_config.go", _http_config_source(self.base_url, self.base_url_expr))
        self._write_generated("transports/http/gen_transport.go", _http_transport_source(self.runtime_import))
        self._write_user_file("transports/http/client.go", _http_public_source(self.runtime_import))

    @property
    def runtime_import(self) -> str:
        return _join_import(self.module, "runtime")

    @contextmanager
    def write_file(self, filepath: str | Path, overwrite: bool = False) -> Generator[IO[str] | None, None, None]:
        path = self.working_dir / filepath
        path.parent.mkdir(parents=True, exist_ok=True)
        wrote = False
        with ensure_filepath_open(str(path), "w", overwrite=overwrite) as handle:
            if handle:
                wrote = True
            yield handle
        if wrote:
            self._written_files.add(path)
            logger.info("[+] Written: %s", path)
        else:
            logger.info("[.] Skipped: %s", path)

    def _write_generated(self, path: str | Path, source: str) -> None:
        with self.write_file(path, overwrite=True) as handle:
            if handle:
                handle.write(source)

    def _write_user_file(self, path: str | Path, source: str) -> None:
        with self.write_file(path, overwrite=False) as handle:
            if handle:
                handle.write(source)

    def _format_written_files(self) -> None:
        if not self._written_files or shutil.which("gofmt") is None:
            return
        subprocess.run(["gofmt", "-w", *[str(path) for path in sorted(self._written_files)]], check=True)


class _TypeNames:
    def __init__(self, schemas: Mapping[str, JsonObject]) -> None:
        base_names: dict[str, list[str]] = {}
        for name in schemas:
            base_names.setdefault(_go_type_name(name), []).append(name)
        self._names = {
            name: (_go_type_name(name) if len(base_names[_go_type_name(name)]) == 1 else _go_type_name(name.replace(".", "_")))
            for name in schemas
        }

    def schema(self, name: object) -> str:
        key = str(name or "")
        return self._names.get(key, _go_type_name(key))

    def ref(self, value: Mapping[str, Any], *, pointer: bool = False) -> str:
        ref = value.get("ref")
        if isinstance(ref, str) and ref:
            target = self.schema(ref)
            return f"*{target}" if pointer else target
        return "any"


def _runtime_client_source() -> str:
    return """// Code generated by api-blueprint (Go client); DO NOT EDIT.

package runtime

import "context"

type Request struct {
	Method string
	Path   string
	Query  any
	JSON   any
	Form   any
	Binary any
}

type ConnectionRequest struct {
	Kind    string
	RouteID string
	Path    string
	Open    any
	Query   any
}

type Transport interface {
	Do(ctx context.Context, request Request, response any) error
	ConnectUnsupported(ctx context.Context, request ConnectionRequest) error
	StreamUnsupported(ctx context.Context, request ConnectionRequest) error
	ChannelUnsupported(ctx context.Context, request ConnectionRequest) error
}

type WebSocket[Send any, Recv any] interface{}
type Stream[Open any, Server any, Close any] interface{}
type Channel[Open any, Server any, Client any, Close any] interface{}

type TransportError = UnsupportedTransportError
"""


def _runtime_errors_source() -> str:
    return """// Code generated by api-blueprint (Go client); DO NOT EDIT.

package runtime

import "fmt"

type UnsupportedTransportError struct {
	Kind    string
	RouteID string
	Path    string
}

func (err UnsupportedTransportError) Error() string {
	return fmt.Sprintf("api-blueprint go client transport does not support %s connections for route %s (%s)", err.Kind, err.RouteID, err.Path)
}

type UnsupportedConnectionError = UnsupportedTransportError

type HTTPError struct {
	StatusCode int
	Body       string
}

func (err HTTPError) Error() string {
	return fmt.Sprintf("api-blueprint http request failed with status %d: %s", err.StatusCode, err.Body)
}
"""


def _runtime_models_source(schemas: Mapping[str, JsonObject], type_names: _TypeNames) -> str:
    enums = _collect_enums(schemas)
    lines = ["// Code generated by api-blueprint (Go client); DO NOT EDIT.", "", "package runtime", ""]
    for enum in enums.values():
        lines.extend(_render_enum(enum))
        lines.append("")
    for schema_name, schema in schemas.items():
        lines.extend(_render_schema(schema_name, schema, type_names))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_schema(schema_name: str, schema: Mapping[str, Any], type_names: _TypeNames) -> list[str]:
    name = type_names.schema(schema_name)
    if schema.get("kind") == "alias" or schema.get("type") == "alias":
        target = schema.get("target")
        target_type = _go_type_for_schema_value(target if isinstance(target, Mapping) else {}, type_names)
        return [f"type {name} = {target_type}"]
    if schema.get("type") != "object":
        return [f"type {name} = {_go_type_for_schema_value(schema, type_names)}"]
    fields = schema.get("fields")
    if not isinstance(fields, Mapping) or not fields:
        return [f"type {name} struct {{}}"]
    lines = [f"type {name} struct {{"]
    for field_name, field_schema in fields.items():
        if not isinstance(field_schema, Mapping):
            continue
        go_field = _go_exported(str(field_schema.get("name") or field_name))
        go_type = _go_type_for_schema_value(field_schema, type_names)
        wire_name = str(field_schema.get("wire_name") or field_schema.get("name") or field_name)
        omitempty = ",omitempty" if field_schema.get("optional") else ""
        tags = f'`json:"{wire_name}{omitempty}" form:"{wire_name}{omitempty}"`'
        lines.append(f"\t{go_field} {go_type} {tags}")
    lines.append("}")
    return lines


def _render_enum(enum: Mapping[str, Any]) -> list[str]:
    name = _go_type_name(str(enum.get("enum") or enum.get("name") or "EnumValue"))
    base_type = _enum_base_type(enum)
    lines = [f"type {name} {base_type}", "", "const ("]
    for member in enum.get("enum_values", []):
        if not isinstance(member, Mapping):
            continue
        member_name = _go_exported(str(member.get("name") or member.get("value") or "Value"))
        lines.append(f"\t{name}{member_name} {name} = {json.dumps(member.get('value'))}")
    lines.append(")")
    return lines


def _group_models_source(
    group: GoClientGroup,
    schemas: Mapping[str, JsonObject],
    type_names: _TypeNames,
    runtime_import: str,
) -> str:
    body: list[str] = []
    emitted_messages: set[str] = set()
    for route in group.routes:
        body.extend(_route_aliases(route, schemas, type_names, emitted_messages))

    lines = [
        "// Code generated by api-blueprint (Go client); DO NOT EDIT.",
        "",
        f"package {group.package}",
        "",
    ]
    if any("runtime." in line for line in body):
        lines.extend([f'import runtime "{runtime_import}"', ""])
    lines.extend(body)
    return "\n".join(lines).rstrip() + "\n"


def _route_aliases(
    route: GoClientRoute,
    schemas: Mapping[str, JsonObject],
    type_names: _TypeNames,
    emitted_messages: set[str],
) -> list[str]:
    lines: list[str] = []
    operation = route.operation
    aliases = (
        (f"REQ_{operation}_QUERY", route.request.get("query_model")),
        (f"REQ_{operation}_JSON", route.request.get("json_model")),
        (f"REQ_{operation}_FORM", route.request.get("form_model")),
        (f"REQ_{operation}_BINARY", route.request.get("binary_model")),
        (f"OPEN_{operation}", route.connection.get("open_model")),
        (f"CLOSE_{operation}", route.connection.get("close_model")),
        (f"RSP_{operation}_BODY", route.response.get("model")),
    )
    for alias, schema_name in aliases:
        if isinstance(schema_name, str) and schema_name:
            schema = schemas.get(schema_name)
            if isinstance(schema, Mapping) and schema.get("auto") is True and schema.get("type") == "object":
                lines.extend(_render_route_schema(alias, schema, type_names))
            else:
                lines.append(f"type {alias} = runtime.{type_names.schema(schema_name)}")
    for message_key in ("server_message", "client_message"):
        message = route.connection.get(message_key)
        if isinstance(message, Mapping) and isinstance(message.get("name"), str):
            if message["name"] in emitted_messages:
                continue
            emitted_messages.add(str(message["name"]))
            lines.append(f"type {message['name']} struct {{")
            lines.append("\tType string `json:\"type\"`")
            lines.append("\tData any `json:\"data,omitempty\"`")
            lines.append("}")
    if lines:
        lines.append("")
    return lines


def _render_route_schema(alias: str, schema: Mapping[str, Any], type_names: _TypeNames) -> list[str]:
    fields = schema.get("fields")
    if not isinstance(fields, Mapping) or not fields:
        return [f"type {alias} struct {{}}"]
    lines = [f"type {alias} struct {{"]
    for field_name, field_schema in fields.items():
        if not isinstance(field_schema, Mapping):
            continue
        go_field = _go_exported(str(field_schema.get("name") or field_name))
        go_type = _go_type_for_route_schema_value(field_schema, type_names)
        wire_name = str(field_schema.get("wire_name") or field_schema.get("name") or field_name)
        omitempty = ",omitempty" if field_schema.get("optional") else ""
        tags = f'`json:"{wire_name}{omitempty}" form:"{wire_name}{omitempty}"`'
        lines.append(f"\t{go_field} {go_type} {tags}")
    lines.append("}")
    return lines


def _group_client_source(group: GoClientGroup, type_names: _TypeNames, runtime_import: str) -> str:
    lines = [
        "// Code generated by api-blueprint (Go client); DO NOT EDIT.",
        "",
        f"package {group.package}",
        "",
        "import (",
        '\t"context"',
        f'\truntime "{runtime_import}"',
        ")",
        "",
        f"type Gen{group.client_class} struct {{",
        "\ttransport runtime.Transport",
        "}",
        "",
        f"func NewGen{group.client_class}(transport runtime.Transport) *Gen{group.client_class} {{",
        f"\treturn &Gen{group.client_class}{{transport: transport}}",
        "}",
        "",
    ]
    for route in group.routes:
        lines.extend(_route_method_source(route, type_names))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _route_method_source(route: GoClientRoute, type_names: _TypeNames) -> list[str]:
    if route.kind == "legacy_ws":
        return _connection_method_source(route, "ConnectUnsupported", _route_params(route, include_open=False))
    if route.kind == "stream":
        return _connection_method_source(route, "StreamUnsupported", _route_params(route, include_open=True))
    if route.kind == "channel":
        return _connection_method_source(route, "ChannelUnsupported", _route_params(route, include_open=True))
    return _rpc_method_source(route, type_names)


def _rpc_method_source(route: GoClientRoute, type_names: _TypeNames) -> list[str]:
    params = _route_params(route, include_open=False)
    response_model = route.response.get("model")
    response_type = f"*RSP_{route.operation}_BODY" if isinstance(response_model, str) and response_model else "any"
    args = ["ctx context.Context", *params]
    lines = [
        f"func (client *Gen{_client_class_for_route(route)}) {route.operation}({', '.join(args)}) ({response_type}, error) {{",
        "\trequest := runtime.Request{",
        f"\t\tMethod: {json.dumps(route.method)},",
        f"\t\tPath:   {json.dumps(route.url)},",
    ]
    for field, value in _runtime_request_fields(route):
        lines.append(f"\t\t{field}: {value},")
    lines.extend(["\t}", "\tvar response RSP_" + route.operation + "_BODY"])
    if response_type == "any":
        lines[-1] = "\tvar response any"
    lines.extend(
        [
            "\tif err := client.transport.Do(ctx, request, &response); err != nil {",
            "\t\treturn nil, err",
            "\t}",
            "\treturn &response, nil",
            "}",
        ]
    )
    if response_type == "any":
        lines[-2] = "\treturn response, nil"
    _ = type_names
    return lines


def _connection_method_source(route: GoClientRoute, transport_method: str, params: list[str]) -> list[str]:
    args = ["ctx context.Context", *params]
    lines = [
        f"func (client *Gen{_client_class_for_route(route)}) {_connection_method_name(route)}({', '.join(args)}) error {{",
        "\trequest := runtime.ConnectionRequest{",
        f"\t\tKind:    {json.dumps(route.kind)},",
        f"\t\tRouteID: {json.dumps(route.route_id)},",
        f"\t\tPath:    {json.dumps(route.url)},",
    ]
    if "openData" in " ".join(params):
        lines.append("\t\tOpen:    openData,")
    if "query" in " ".join(params):
        lines.append("\t\tQuery:   query,")
    lines.extend(["\t}", f"\treturn client.transport.{transport_method}(ctx, request)", "}"])
    return lines


def _connection_method_name(route: GoClientRoute) -> str:
    if route.kind == "legacy_ws":
        return f"Connect{route.operation}"
    if route.kind == "stream":
        return f"Subscribe{route.operation}"
    if route.kind == "channel":
        return f"Open{route.operation}"
    return route.operation


def _client_class_for_route(route: GoClientRoute) -> str:
    service_id = str(route.route.get("service_id") or "api")
    group = service_id.split(".", 1)[1] if "." in service_id else service_id
    return f"{_go_exported(group or service_id)}Client"


def _route_params(route: GoClientRoute, *, include_open: bool) -> list[str]:
    params: list[str] = []
    if isinstance(route.request.get("query_model"), str):
        params.append(f"query *REQ_{route.operation}_QUERY")
    if isinstance(route.request.get("json_model"), str):
        params.append(f"jsonBody *REQ_{route.operation}_JSON")
    if isinstance(route.request.get("form_model"), str):
        params.append(f"formBody *REQ_{route.operation}_FORM")
    if isinstance(route.request.get("binary_model"), str):
        params.append(f"binaryBody *REQ_{route.operation}_BINARY")
    if include_open and isinstance(route.connection.get("open_model"), str):
        params.append(f"openData *OPEN_{route.operation}")
    return params


def _runtime_request_fields(route: GoClientRoute) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    if isinstance(route.request.get("query_model"), str):
        fields.append(("Query", "query"))
    if isinstance(route.request.get("json_model"), str):
        fields.append(("JSON", "jsonBody"))
    if isinstance(route.request.get("form_model"), str):
        fields.append(("Form", "formBody"))
    if isinstance(route.request.get("binary_model"), str):
        fields.append(("Binary", "binaryBody"))
    return fields


def _group_public_source(group: GoClientGroup) -> str:
    return f"""package {group.package}

type {group.client_class} = Gen{group.client_class}

var New{group.client_class} = NewGen{group.client_class}
"""


def _http_config_source(base_url: str, base_url_expr: str | None) -> str:
    rendered_base_url = base_url_expr if base_url_expr is not None else json.dumps(base_url)
    return f"""// Code generated by api-blueprint (Go client); DO NOT EDIT.

package http

import nethttp "net/http"

type HttpConfig struct {{
	BaseURL string
	Client  *nethttp.Client
}}

func DefaultHttpConfig() HttpConfig {{
	return HttpConfig{{BaseURL: {rendered_base_url}}}
}}
"""


def _http_transport_source(runtime_import: str) -> str:
    return f"""// Code generated by api-blueprint (Go client); DO NOT EDIT.

package http

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	nethttp "net/http"
	"net/url"
	"reflect"
	"strings"

	runtime "{runtime_import}"
)

type HttpTransport struct {{
	config HttpConfig
	client *nethttp.Client
}}

func NewHttpTransport(config HttpConfig) *HttpTransport {{
	client := config.Client
	if client == nil {{
		client = nethttp.DefaultClient
	}}
	return &HttpTransport{{config: config, client: client}}
}}

var _ = runtime.UnsupportedConnectionError{{}}

func (transport *HttpTransport) Do(ctx context.Context, request runtime.Request, response any) error {{
	endpoint, err := joinURL(transport.config.BaseURL, request.Path)
	if err != nil {{
		return err
	}}
	if request.Query != nil {{
		query, err := encodeValues(request.Query)
		if err != nil {{
			return err
		}}
		endpoint.RawQuery = query.Encode()
	}}

	body, contentType, err := encodeBody(request)
	if err != nil {{
		return err
	}}
	httpRequest, err := nethttp.NewRequestWithContext(ctx, request.Method, endpoint.String(), body)
	if err != nil {{
		return err
	}}
	if contentType != "" {{
		httpRequest.Header.Set("Content-Type", contentType)
	}}
	httpRequest.Header.Set("Accept", "application/json")

	httpResponse, err := transport.client.Do(httpRequest)
	if err != nil {{
		return err
	}}
	defer httpResponse.Body.Close()

	if httpResponse.StatusCode >= 400 {{
		data, _ := io.ReadAll(httpResponse.Body)
		return runtime.HTTPError{{StatusCode: httpResponse.StatusCode, Body: string(data)}}
	}}
	if response == nil || httpResponse.StatusCode == nethttp.StatusNoContent {{
		return nil
	}}
	return json.NewDecoder(httpResponse.Body).Decode(response)
}}

func (transport *HttpTransport) ConnectUnsupported(ctx context.Context, request runtime.ConnectionRequest) error {{
	return runtime.UnsupportedTransportError{{Kind: request.Kind, RouteID: request.RouteID, Path: request.Path}}
}}

func (transport *HttpTransport) StreamUnsupported(ctx context.Context, request runtime.ConnectionRequest) error {{
	return runtime.UnsupportedTransportError{{Kind: request.Kind, RouteID: request.RouteID, Path: request.Path}}
}}

func (transport *HttpTransport) ChannelUnsupported(ctx context.Context, request runtime.ConnectionRequest) error {{
	return runtime.UnsupportedTransportError{{Kind: request.Kind, RouteID: request.RouteID, Path: request.Path}}
}}

func joinURL(base string, path string) (*url.URL, error) {{
	if base == "" {{
		base = "http://localhost"
	}}
	endpoint, err := url.Parse(strings.TrimRight(base, "/") + "/" + strings.TrimLeft(path, "/"))
	if err != nil {{
		return nil, err
	}}
	return endpoint, nil
}}

func encodeBody(request runtime.Request) (io.Reader, string, error) {{
	switch {{
	case request.Binary != nil:
		data, err := json.Marshal(request.Binary)
		return bytes.NewReader(data), "application/octet-stream", err
	case request.Form != nil:
		values, err := encodeValues(request.Form)
		if err != nil {{
			return nil, "", err
		}}
		return strings.NewReader(values.Encode()), "application/x-www-form-urlencoded", nil
	case request.JSON != nil:
		data, err := json.Marshal(request.JSON)
		return bytes.NewReader(data), "application/json", err
	default:
		return nil, "", nil
	}}
}}

func encodeValues(input any) (url.Values, error) {{
	values := url.Values{{}}
	if input == nil {{
		return values, nil
	}}
	value := reflect.ValueOf(input)
	if value.Kind() == reflect.Pointer {{
		if value.IsNil() {{
			return values, nil
		}}
		value = value.Elem()
	}}
	if value.Kind() != reflect.Struct {{
		return values, fmt.Errorf("api-blueprint http transport expected struct values, got %s", value.Kind())
	}}
	valueType := value.Type()
	for i := 0; i < value.NumField(); i++ {{
		field := value.Field(i)
		fieldType := valueType.Field(i)
		key := fieldType.Tag.Get("form")
		if key == "" {{
			key = fieldType.Tag.Get("json")
		}}
		key = strings.Split(key, ",")[0]
		if key == "" || key == "-" {{
			key = fieldType.Name
		}}
		if field.IsZero() {{
			continue
		}}
		values.Set(key, fmt.Sprint(field.Interface()))
	}}
	return values, nil
}}
"""


def _http_public_source(runtime_import: str) -> str:
    return f"""package http

import runtime "{runtime_import}"

func NewClient(config HttpConfig) runtime.Transport {{
	return NewHttpTransport(config)
}}
"""


def _go_type_for_schema_value(value: Mapping[str, Any], type_names: _TypeNames) -> str:
    value_type = str(value.get("type") or "any")
    if value_type == "object" and value.get("ref"):
        return type_names.ref(value, pointer=True)
    if value_type == "array":
        items = value.get("items")
        if isinstance(items, Mapping):
            item_type = _go_type_for_schema_value(items, type_names)
            return f"[]{item_type}"
        return "[]any"
    if value_type == "map":
        keys = value.get("keys")
        values = value.get("values")
        key_type = _go_type_for_schema_value(keys if isinstance(keys, Mapping) else {"type": "string"}, type_names)
        value_go_type = _go_type_for_schema_value(values if isinstance(values, Mapping) else {"type": "any"}, type_names)
        return f"map[{key_type}]{value_go_type}"
    if value_type == "enum":
        return _go_type_name(str(value.get("enum") or "EnumValue"))
    return {
        "string": "string",
        "str": "string",
        "int": "int",
        "integer": "int",
        "int64": "int64",
        "int32": "int32",
        "int16": "int16",
        "int8": "int8",
        "uint": "uint",
        "uint64": "uint64",
        "uint32": "uint32",
        "uint16": "uint16",
        "uint8": "uint8",
        "float": "float64",
        "float64": "float64",
        "float32": "float32",
        "number": "float64",
        "boolean": "bool",
        "bool": "bool",
        "binary": "[]byte",
        "any": "any",
        "null": "any",
    }.get(value_type, "any")


def _go_type_for_route_schema_value(value: Mapping[str, Any], type_names: _TypeNames) -> str:
    value_type = str(value.get("type") or "any")
    if value_type == "object" and value.get("ref"):
        return f"*runtime.{type_names.ref(value, pointer=False)}"
    if value_type == "array":
        items = value.get("items")
        if isinstance(items, Mapping):
            return f"[]{_go_type_for_route_schema_value(items, type_names)}"
        return "[]any"
    if value_type == "map":
        keys = value.get("keys")
        values = value.get("values")
        key_type = _go_type_for_route_schema_value(keys if isinstance(keys, Mapping) else {"type": "string"}, type_names)
        value_go_type = _go_type_for_route_schema_value(values if isinstance(values, Mapping) else {"type": "any"}, type_names)
        return f"map[{key_type}]{value_go_type}"
    if value_type == "enum":
        return f"runtime.{_go_type_name(str(value.get('enum') or 'EnumValue'))}"
    return _go_type_for_schema_value(value, type_names)


def _collect_enums(schemas: Mapping[str, JsonObject]) -> dict[str, Mapping[str, Any]]:
    enums: dict[str, Mapping[str, Any]] = {}

    def visit(value: object) -> None:
        if isinstance(value, Mapping):
            if value.get("type") == "enum" and isinstance(value.get("enum"), str):
                enums[str(value["enum"])] = value
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schemas)
    return enums


def _enum_base_type(enum: Mapping[str, Any]) -> str:
    values = enum.get("values")
    first = values[0] if isinstance(values, list) and values else None
    if isinstance(first, bool):
        return "bool"
    if isinstance(first, int):
        return "int"
    if isinstance(first, float):
        return "float64"
    return "string"


def _build_groups(routes: Sequence[JsonObject], services: Mapping[str, JsonObject]) -> tuple[GoClientGroup, ...]:
    groups: dict[tuple[str, ...], GoClientGroup] = {}
    for route in routes:
        service = services.get(str(route.get("service_id") or ""), {})
        root = _path_segment(str(service.get("root") or _service_root(route)), default="api")
        group_name = _path_segment(str(service.get("group") or root), default=root)
        segments = (root,) if group_name == root else (root, group_name)
        group = groups.get(segments)
        if group is None:
            package = _go_package_name(segments[-1])
            group = GoClientGroup(
                segments=segments,
                package=package,
                client_class=f"{_go_exported(group_name)}Client",
            )
            groups[segments] = group
        group.routes.append(GoClientRoute(route))
    return tuple(groups.values())


def _service_root(route: Mapping[str, Any]) -> str:
    service_id = str(route.get("service_id") or "api")
    return service_id.split(".", 1)[0]


def _list_of_maps(value: object) -> list[JsonObject]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _mapping_of_maps(value: object) -> dict[str, JsonObject]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): dict(item) for key, item in value.items() if isinstance(item, Mapping)}


def _mapping_of_maps_by_id(value: object) -> dict[str, JsonObject]:
    result: dict[str, JsonObject] = {}
    for item in _list_of_maps(value):
        item_id = item.get("id")
        if isinstance(item_id, str):
            result[item_id] = item
    return result


def _go_type_name(value: str) -> str:
    if "." in value:
        value = value.rsplit(".", 1)[-1]
    return _go_exported(value)


def _go_exported(value: str) -> str:
    parts = [part for part in re.split(r"[^0-9A-Za-z_]+", value) if part]
    if not parts:
        return "Value"
    result = "".join(part[:1].upper() + part[1:] for part in parts)
    if result[:1].isdigit():
        result = "Value" + result
    return result


def _go_package_name(value: str) -> str:
    package = re.sub(r"[^0-9A-Za-z_]+", "_", value.lower()).strip("_")
    if not package:
        return "api"
    if package[0].isdigit():
        package = "p_" + package
    return package


def _path_segment(value: str, *, default: str) -> str:
    segment = re.sub(r"[^0-9A-Za-z_]+", "_", value.strip("/").lower()).strip("_")
    return segment or default


def _join_import(*parts: str) -> str:
    return "/".join(part.strip("/") for part in parts if part.strip("/"))
