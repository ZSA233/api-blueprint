from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from api_blueprint.writer.core.sdk_names import go_exported_field_name


JsonObject = dict[str, Any]

GO_SCALAR_TYPES = {
    "u8": "uint8",
    "u16": "uint16",
    "u24": "uint32",
    "u32": "uint32",
    "u64": "uint64",
    "i8": "int8",
    "i16": "int16",
    "i24": "int32",
    "i32": "int32",
    "i64": "int64",
    "f32": "float32",
    "f64": "float64",
    "bool": "bool",
    "string": "string",
}
WRITE_METHODS = {
    "u8": "WriteUint8",
    "u16": "WriteUint16",
    "u24": "WriteUint24",
    "u32": "WriteUint32",
    "u64": "WriteUint64",
    "i8": "WriteInt8",
    "i16": "WriteInt16",
    "i24": "WriteInt24",
    "i32": "WriteInt32",
    "i64": "WriteInt64",
    "f32": "WriteFloat32",
    "f64": "WriteFloat64",
    "bool": "WriteBool",
}
READ_METHODS = {
    "u8": "ReadUint8",
    "u16": "ReadUint16",
    "u24": "ReadUint24",
    "u32": "ReadUint32",
    "u64": "ReadUint64",
    "i8": "ReadInt8",
    "i16": "ReadInt16",
    "i24": "ReadInt24",
    "i32": "ReadInt32",
    "i64": "ReadInt64",
    "f32": "ReadFloat32",
    "f64": "ReadFloat64",
    "bool": "ReadBool",
}
INTEGER_TYPES = {"u8", "u16", "u24", "u32", "u64", "i8", "i16", "i24", "i32", "i64"}
SIGNED_INTEGER_TYPES = {"i8", "i16", "i24", "i32", "i64"}
EXPR_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[()+\-*/]")


def go_name(value: str) -> str:
    return go_exported_field_name(value, fallback="Value")


def _scope_go_name(schema_name: str, raw_name: str) -> str:
    schema_type = go_name(schema_name)
    raw_type = go_name(raw_name)
    return raw_type if raw_type.startswith(schema_type) else f"{schema_type}{raw_type}"


def _unexported_go_name(name: str) -> str:
    return name[:1].lower() + name[1:] if name else "value"


def _generated_name_key(value: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", value.lower())


def compile_go_uint_expr(expr: str) -> str:
    tokens = EXPR_TOKEN_RE.findall(expr)
    compact = "".join(tokens)
    expected = re.sub(r"\s+", "", expr)
    if compact != expected or not tokens:
        raise ValueError(f"unsupported binary expression: {expr}")
    rendered: list[str] = []
    for token in tokens:
        if token.isdigit():
            rendered.append(f"uint64({token})")
        elif token in {"+", "-", "*", "/", "(", ")"}:
            rendered.append(token)
        else:
            rendered.append(f"uint64(state.{go_name(token)})")
    return " ".join(rendered)


def compile_go_int_expr(expr: str) -> str:
    tokens = EXPR_TOKEN_RE.findall(expr)
    compact = "".join(tokens)
    expected = re.sub(r"\s+", "", expr)
    if compact != expected or not tokens:
        raise ValueError(f"unsupported binary expression: {expr}")
    rendered: list[str] = []
    for token in tokens:
        if token.isdigit():
            rendered.append(f"int64({token})")
        elif token in {"+", "-", "*", "/", "(", ")"}:
            rendered.append(token)
        else:
            rendered.append(f"int64(state.{go_name(token)})")
    return " ".join(rendered)


def go_string(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


@dataclass(frozen=True)
class GoClientBinaryValue:
    raw: Mapping[str, Any]
    value_set: "GoClientBinaryValueSet"

    @property
    def name(self) -> str:
        return str(self.raw.get("name") or "")

    @property
    def go_name(self) -> str:
        return go_name(self.name)

    @property
    def value(self) -> str:
        return str(self.raw.get("value") or "0")

    @property
    def rule(self) -> Mapping[str, str]:
        value = self.raw.get("rule")
        return value if isinstance(value, Mapping) else {}

    @property
    def bit_start(self) -> int:
        value = self.raw.get("bit_start")
        if isinstance(value, int):
            return value
        return self._parsed_bit_range()[0]

    @property
    def bit_end(self) -> int:
        value = self.raw.get("bit_end")
        if isinstance(value, int):
            return value
        return self._parsed_bit_range()[1]

    @property
    def enum_name(self) -> str | None:
        value = self.rule.get("enum")
        return self.value_set.schema.value_set_type_name(str(value)) if value else None

    @property
    def is_reserved_zero(self) -> bool:
        return self.rule.get("const") == "0"

    @property
    def is_single_bit_flag(self) -> bool:
        return (
            self.value_set.kind == "bitflags"
            and self._has_bit_range()
            and self.bit_start == self.bit_end
            and not self.is_reserved_zero
            and self.enum_name is None
        )

    @property
    def is_enum_bitfield(self) -> bool:
        return (
            self.value_set.kind == "bitflags"
            and self._has_bit_range()
            and not self.is_reserved_zero
            and self.enum_name is not None
        )

    def _has_bit_range(self) -> bool:
        return any(key in self.raw for key in ("bit", "bits", "bit_start", "bit_end"))

    def _parsed_bit_range(self) -> tuple[int, int]:
        raw = str(self.raw.get("bits") or self.raw.get("bit") or "0").strip()
        if ".." in raw:
            start, end = [part.strip() for part in raw.split("..", 1)]
        else:
            start = end = raw
        if not start.isdigit() or not end.isdigit():
            return 0, 0
        return int(start), int(end)


@dataclass(frozen=True)
class GoClientBinaryValueSet:
    raw: Mapping[str, Any]
    schema: "GoClientBinarySchema"

    @property
    def name(self) -> str:
        return str(self.raw.get("name") or "ValueSet")

    @property
    def go_type(self) -> str:
        return self.schema.value_set_type_name(self.name)

    @property
    def wire_type(self) -> str:
        return str(self.raw.get("base_type") or "u32")

    @property
    def kind(self) -> str:
        return str(self.raw.get("kind") or "enum")

    @property
    def base_type(self) -> str:
        return GO_SCALAR_TYPES.get(self.wire_type, "uint32")

    @property
    def values(self) -> list[GoClientBinaryValue]:
        return [GoClientBinaryValue(value, self) for value in _list_of_maps(self.raw.get("values"))]

    @property
    def const_values(self) -> list[GoClientBinaryValue]:
        return [value for value in self.values if not value.is_reserved_zero]

    @property
    def reserved_zero_mask(self) -> int:
        value = self.raw.get("reserved_zero_mask")
        return int(value) if isinstance(value, int) else 0

    @property
    def reserved_mask_name(self) -> str:
        return "ReservedMask"

    @property
    def single_bit_flags(self) -> list[GoClientBinaryValue]:
        return [value for value in self.values if value.is_single_bit_flag]

    @property
    def enum_bitfields(self) -> list[GoClientBinaryValue]:
        return [value for value in self.values if value.is_enum_bitfield]

    @property
    def has_helpers(self) -> bool:
        return self.kind == "bitflags" and (
            bool(self.single_bit_flags) or bool(self.enum_bitfields) or self.reserved_zero_mask != 0
        )


@dataclass(frozen=True)
class GoClientBinaryField:
    raw: Mapping[str, Any]
    schema: "GoClientBinarySchema"

    @property
    def name(self) -> str:
        return str(self.raw.get("field") or self.raw.get("name") or "")

    @property
    def go_name(self) -> str:
        return go_name(self.name)

    @property
    def typ(self) -> str:
        return str(self.raw.get("type") or "bytes")

    @property
    def value_type(self) -> GoClientBinaryValueSet | None:
        return self.schema.value_type_map.get(self.typ)

    @property
    def wire_type(self) -> str:
        return self.value_type.wire_type if self.value_type is not None else self.typ

    @property
    def count(self) -> str:
        return str(self.raw.get("count") or "1")

    @property
    def rule(self) -> Mapping[str, str]:
        value = self.raw.get("rule")
        return value if isinstance(value, Mapping) else {}

    @property
    def is_array(self) -> bool:
        return self.count not in {"", "1"}

    @property
    def is_bytes(self) -> bool:
        return self.typ == "bytes"

    @property
    def is_string(self) -> bool:
        return self.typ == "string"

    @property
    def is_padding(self) -> bool:
        return self.typ == "padding"

    @property
    def is_reserved(self) -> bool:
        return self.typ == "reserved"

    @property
    def is_hidden(self) -> bool:
        return self.is_padding or self.is_reserved

    @property
    def is_scalar(self) -> bool:
        return self.wire_type in GO_SCALAR_TYPES and self.wire_type != "string"

    @property
    def is_integer_scalar(self) -> bool:
        return self.wire_type in INTEGER_TYPES

    @property
    def is_signed_integer_scalar(self) -> bool:
        return self.wire_type in SIGNED_INTEGER_TYPES

    @property
    def bitflags_zero_mask(self) -> int:
        value_type = self.value_type
        if value_type is None or value_type.kind != "bitflags":
            return 0
        return value_type.reserved_zero_mask

    @property
    def has_default(self) -> bool:
        return "const" in self.rule

    @property
    def go_type(self) -> str:
        if self.is_bytes:
            return "[]byte"
        if self.is_string:
            return "string"
        single = self.single_go_type
        if self.is_array:
            return f"[]{single}"
        return single

    @property
    def single_go_type(self) -> str:
        if self.value_type is not None:
            return self.value_type.go_type
        return GO_SCALAR_TYPES.get(self.typ, self.schema.object_type_name(self.typ))

    @property
    def value_expr(self) -> str:
        if self.has_default:
            return self.const_expr
        return f"value.{self.go_name}"

    @property
    def numeric_value_expr(self) -> str:
        if self.wire_type == "bool":
            return self.value_expr
        if self.is_signed_integer_scalar:
            return f"int64({self.value_expr})"
        return f"uint64({self.value_expr})"

    def numeric_expr(self, expr: str) -> str:
        if self.wire_type == "bool":
            return expr
        if self.is_signed_integer_scalar:
            return f"int64({expr})"
        return f"uint64({expr})"

    def writer_expr(self, expr: str) -> str:
        if self.value_type is None:
            return expr
        return f"{GO_SCALAR_TYPES.get(self.wire_type, 'uint64')}({expr})"

    def reader_expr(self, expr: str) -> str:
        if self.value_type is None:
            return expr
        return f"{self.value_type.go_type}({expr})"

    @property
    def const_expr(self) -> str:
        raw = str(self.rule.get("const") or "0")
        if self.is_bytes:
            return f"[]byte({go_string(raw)})"
        if self.is_string:
            return go_string(raw)
        if self.wire_type == "bool":
            return "true" if raw.lower() in {"1", "true"} else "false"
        if self.value_type is not None:
            return f"{self.value_type.go_type}({raw})"
        return raw

    @property
    def count_expr(self) -> str:
        return compile_go_uint_expr(self.count)

    @property
    def min_expr(self) -> str:
        raw = str(self.rule.get("min") or "0")
        return compile_go_int_expr(raw) if self.is_signed_integer_scalar else compile_go_uint_expr(raw)

    @property
    def max_expr(self) -> str:
        raw = str(self.rule.get("max") or "0")
        return compile_go_int_expr(raw) if self.is_signed_integer_scalar else compile_go_uint_expr(raw)

    @property
    def assert_expr(self) -> str:
        raw = str(self.rule.get("assert") or "0")
        return compile_go_int_expr(raw) if self.is_signed_integer_scalar else compile_go_uint_expr(raw)

    @property
    def write_method(self) -> str:
        return WRITE_METHODS[self.wire_type]

    @property
    def read_method(self) -> str:
        return READ_METHODS[self.wire_type]

    @property
    def sizeof_name(self) -> str | None:
        value = self.rule.get("sizeof")
        return str(value) if value else None

    @property
    def sizeof_go_name(self) -> str | None:
        return go_name(self.sizeof_name) if self.sizeof_name else None


@dataclass(frozen=True)
class GoClientBinaryObject:
    raw: Mapping[str, Any]
    schema: "GoClientBinarySchema"

    @property
    def name(self) -> str:
        return str(self.raw.get("name") or "")

    @property
    def go_type(self) -> str:
        return self.schema.object_type_name(self.name)

    @property
    def fields(self) -> list[GoClientBinaryField]:
        return [GoClientBinaryField(field, self.schema) for field in _list_of_maps(self.raw.get("fields"))]

    @property
    def data_fields(self) -> list[GoClientBinaryField]:
        return [field for field in self.fields if not field.is_hidden and not field.has_default]

    def has_public_field(self, name: str | None) -> bool:
        if not name:
            return False
        return any(field.name == name and not field.is_hidden and not field.has_default for field in self.fields)


@dataclass(frozen=True)
class GoClientBinarySchema:
    raw: Mapping[str, Any]

    @property
    def name(self) -> str:
        return str(self.raw.get("name") or "Packet")

    @property
    def go_type(self) -> str:
        return go_name(self.name)

    @property
    def state_type(self) -> str:
        return f"{_unexported_go_name(self.go_type)}BinaryState"

    @property
    def content_type(self) -> str:
        return str(self.raw.get("content_type") or "application/octet-stream")

    @property
    def endian(self) -> str:
        return "runtimebinary.BigEndian" if self.raw.get("endian") == "big" else "runtimebinary.LittleEndian"

    @property
    def sections(self) -> list[GoClientBinaryObject]:
        return [GoClientBinaryObject(section, self) for section in _list_of_maps(self.raw.get("sections"))]

    @property
    def structs(self) -> list[GoClientBinaryObject]:
        return [GoClientBinaryObject(struct, self) for struct in _list_of_maps(self.raw.get("structs"))]

    @property
    def objects(self) -> list[GoClientBinaryObject]:
        return [*self.sections, *self.structs]

    @property
    def value_sets(self) -> list[GoClientBinaryValueSet]:
        raw = [*_list_of_maps(self.raw.get("enums")), *_list_of_maps(self.raw.get("bitflags"))]
        return [GoClientBinaryValueSet(item, self) for item in raw]

    @property
    def value_type_map(self) -> dict[str, GoClientBinaryValueSet]:
        return {value_set.name: value_set for value_set in self.value_sets}

    @property
    def state_fields(self) -> list[str]:
        seen: set[str] = set()
        fields: list[str] = []
        for obj in self.objects:
            for field in obj.fields:
                if field.name in seen or field.count != "1" or not field.is_integer_scalar:
                    continue
                seen.add(field.name)
                fields.append(field.name)
        return fields

    @property
    def state_fields_go(self) -> list[str]:
        return [go_name(field) for field in self.state_fields]

    def packet_field_name(self, section_name: str) -> str:
        suffix = section_name.removeprefix(self.name)
        return go_name(suffix or section_name)

    def object_type_name(self, object_name: str) -> str:
        return _scope_go_name(self.name, object_name)

    def value_set_type_name(self, value_set_name: str) -> str:
        return _scope_go_name(self.name, value_set_name)


def unique_go_client_binary_schemas(schemas: Iterable[Mapping[str, Any]]) -> list[GoClientBinarySchema]:
    unique: dict[str, Mapping[str, Any]] = {}
    generated_names: dict[str, str] = {}
    for schema in schemas:
        name = str(schema.get("name") or "")
        if not name:
            continue
        generated_name = _generated_name_key(name)
        previous = generated_names.get(generated_name)
        if previous is not None and previous != name:
            raise ValueError(f"duplicate binary schema generated name {go_name(name)}: {previous}, {name}")
        generated_names[generated_name] = name
        unique.setdefault(name, schema)
    return [GoClientBinarySchema(schema) for schema in unique.values()]


def _list_of_maps(value: object) -> list[JsonObject]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]
