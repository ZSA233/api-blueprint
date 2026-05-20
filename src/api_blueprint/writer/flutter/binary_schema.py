from __future__ import annotations

import json
import re
from dataclasses import dataclass

from api_blueprint.engine.binary_schema import BinaryField, BinaryObject, BinarySchema

from .naming import to_dart_identifier, to_dart_type_name


DART_BINARY_SCALAR_TYPES: dict[str, str] = {
    "u8": "int",
    "u16": "int",
    "u24": "int",
    "u32": "int",
    "u64": "int",
    "i8": "int",
    "i16": "int",
    "i24": "int",
    "i32": "int",
    "i64": "int",
    "f32": "double",
    "f64": "double",
    "bool": "bool",
    "string": "String",
}
INTEGER_TYPES = {"u8", "u16", "u24", "u32", "u64", "i8", "i16", "i24", "i32", "i64"}
WRITE_METHODS: dict[str, str] = {
    "u8": "writeU8",
    "u16": "writeU16",
    "u24": "writeU24",
    "u32": "writeU32",
    "u64": "writeU64",
    "i8": "writeI8",
    "i16": "writeI16",
    "i24": "writeI24",
    "i32": "writeI32",
    "i64": "writeI64",
    "f32": "writeF32",
    "f64": "writeF64",
    "bool": "writeBool",
}
READ_METHODS: dict[str, str] = {
    "u8": "readU8",
    "u16": "readU16",
    "u24": "readU24",
    "u32": "readU32",
    "u64": "readU64",
    "i8": "readI8",
    "i16": "readI16",
    "i24": "readI24",
    "i32": "readI32",
    "i64": "readI64",
    "f32": "readF32",
    "f64": "readF64",
    "bool": "readBool",
}
EXPR_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[()+\-*/]")


def dart_binary_expr(expr: str) -> str:
    tokens = EXPR_TOKEN_RE.findall(expr)
    compact = "".join(tokens)
    expected = re.sub(r"\s+", "", expr)
    if compact != expected or not tokens:
        raise ValueError(f"unsupported binary expression: {expr}")
    rendered: list[str] = []
    for token in tokens:
        if token.isdigit() or token in {"+", "-", "*", "/", "(", ")"}:
            rendered.append(token)
        else:
            rendered.append(f"(state[{json.dumps(to_dart_identifier(token))}] ?? 0)")
    return " ".join(rendered)


def dart_string_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False).replace("$", r"\$")


def dart_bytes_literal(value: str) -> str:
    return f"Uint8List.fromList([{', '.join(str(item) for item in value.encode('utf-8'))}])"


@dataclass(frozen=True)
class FlutterBinaryField:
    field: BinaryField
    schema: "FlutterBinarySchema"

    @property
    def name(self) -> str:
        return self.field.name

    @property
    def dart_name(self) -> str:
        return to_dart_identifier(self.field.name)

    @property
    def typ(self) -> str:
        return self.field.type

    @property
    def value_type(self):
        return self.schema.schema.value_type_map().get(self.typ)

    @property
    def wire_type(self) -> str:
        return self.value_type.base_type if self.value_type is not None else self.typ

    @property
    def count(self) -> str:
        return self.field.count

    @property
    def rule(self) -> dict[str, str]:
        return dict(self.field.rule)

    @property
    def is_hidden(self) -> bool:
        return self.typ in {"padding", "reserved"}

    @property
    def is_bytes(self) -> bool:
        return self.typ == "bytes"

    @property
    def is_string(self) -> bool:
        return self.typ == "string"

    @property
    def is_array(self) -> bool:
        return self.field.is_array

    @property
    def is_scalar(self) -> bool:
        return self.wire_type in DART_BINARY_SCALAR_TYPES and self.wire_type != "string"

    @property
    def is_integer_scalar(self) -> bool:
        return self.wire_type in INTEGER_TYPES

    @property
    def dart_type(self) -> str:
        if self.is_bytes:
            return "Uint8List"
        if self.is_string:
            return "String"
        if self.is_array:
            return f"List<{self.single_dart_type}>"
        return self.single_dart_type

    @property
    def single_dart_type(self) -> str:
        if self.value_type is not None:
            return "int"
        return DART_BINARY_SCALAR_TYPES.get(self.typ, self.schema.object_type_name(self.typ))

    @property
    def write_method(self) -> str:
        return WRITE_METHODS[self.wire_type]

    @property
    def read_method(self) -> str:
        return READ_METHODS[self.wire_type]

    @property
    def const_value(self) -> str | None:
        return self.rule.get("const")

    @property
    def has_default(self) -> bool:
        return self.const_value is not None

    @property
    def default_expr(self) -> str | None:
        raw = self.const_value
        if raw is None:
            return None
        if self.is_bytes:
            return dart_bytes_literal(raw)
        if self.is_string:
            return dart_string_literal(raw)
        if self.wire_type == "bool":
            return "true" if raw.lower() in {"1", "true"} else "false"
        return dart_binary_expr(raw)

    @property
    def count_expr(self) -> str:
        return dart_binary_expr(self.count)

    @property
    def min_expr(self) -> str:
        return dart_binary_expr(self.rule.get("min", "0"))

    @property
    def max_expr(self) -> str:
        return dart_binary_expr(self.rule.get("max", "0"))

    @property
    def assert_expr(self) -> str:
        return dart_binary_expr(self.rule.get("assert", "0"))

    @property
    def const_expr(self) -> str:
        return self.default_expr or dart_binary_expr("0")

    @property
    def supports_numeric_rules(self) -> bool:
        return self.is_integer_scalar

    @property
    def bitflags_zero_mask(self) -> int:
        value_type = self.value_type
        if value_type is None or value_type.kind != "bitflags":
            return 0
        return value_type.reserved_zero_mask

    @property
    def sizeof_name(self) -> str | None:
        return self.rule.get("sizeof")

    @property
    def sizeof_dart_name(self) -> str | None:
        return to_dart_identifier(self.sizeof_name) if self.sizeof_name else None

    @property
    def required_value_expr(self) -> str:
        field_path = f"apiBinaryJoinPath(path, {dart_string_literal(self.name)})"
        if self.default_expr is not None:
            return f"value.{self.dart_name} ?? {self.default_expr}"
        return f"apiBinaryRequire<{self.dart_type}>(value.{self.dart_name}, {field_path})"


@dataclass(frozen=True)
class FlutterBinaryObject:
    obj: BinaryObject
    schema: "FlutterBinarySchema"

    @property
    def name(self) -> str:
        return self.obj.name

    @property
    def dart_name(self) -> str:
        return self.schema.object_type_name(self.obj.name)

    @property
    def var_name(self) -> str:
        return to_dart_identifier(self.dart_name)

    @property
    def fields(self) -> tuple[FlutterBinaryField, ...]:
        return tuple(FlutterBinaryField(field, self.schema) for field in self.obj.fields)

    @property
    def data_fields(self) -> tuple[FlutterBinaryField, ...]:
        return tuple(field for field in self.fields if not field.is_hidden)

    @property
    def writer_name(self) -> str:
        return f"_write{self.dart_name}"

    @property
    def reader_name(self) -> str:
        return f"_read{self.dart_name}"

    def has_public_field(self, name: str | None) -> bool:
        return bool(name) and any(field.name == name and not field.is_hidden for field in self.fields)


@dataclass(frozen=True)
class FlutterBinaryValueSet:
    value_set: object
    schema: "FlutterBinarySchema"

    @property
    def name(self) -> str:
        return self.schema.value_set_type_name(self.value_set.name)

    @property
    def values_class(self) -> str:
        return f"{self.name}Values"

    @property
    def values(self):
        return self.value_set.values

    def value_name(self, name: str) -> str:
        return to_dart_identifier(name)


@dataclass(frozen=True)
class FlutterBinarySchema:
    schema: BinarySchema

    @property
    def name(self) -> str:
        return to_dart_type_name(self.schema.name)

    @property
    def endian_expr(self) -> str:
        return "Endian.big" if self.schema.endian == "big" else "Endian.little"

    @property
    def content_type(self) -> str:
        return self.schema.content_type

    @property
    def sections(self) -> tuple[FlutterBinaryObject, ...]:
        return tuple(FlutterBinaryObject(section, self) for section in self.schema.sections)

    @property
    def structs(self) -> tuple[FlutterBinaryObject, ...]:
        return tuple(FlutterBinaryObject(obj, self) for obj in self.schema.structs.values())

    @property
    def all_objects(self) -> tuple[FlutterBinaryObject, ...]:
        return (*self.sections, *self.structs)

    @property
    def value_sets(self) -> tuple[FlutterBinaryValueSet, ...]:
        values = (*self.schema.enums.values(), *self.schema.bitflags.values())
        return tuple(FlutterBinaryValueSet(value, self) for value in values)

    @property
    def packet_fields(self) -> tuple[FlutterBinaryField, ...]:
        fields: list[FlutterBinaryField] = []
        seen: set[str] = set()
        for section in self.sections:
            for field in section.data_fields:
                if field.name in seen:
                    continue
                seen.add(field.name)
                fields.append(field)
        return tuple(fields)

    @property
    def state_fields(self) -> tuple[str, ...]:
        seen: set[str] = set()
        fields: list[str] = []
        for obj in self.all_objects:
            for field in obj.fields:
                if field.name in seen or field.count != "1" or not field.is_integer_scalar:
                    continue
                seen.add(field.name)
                fields.append(field.dart_name)
        return tuple(fields)

    @property
    def encode_func(self) -> str:
        return f"encode{self.name}"

    @property
    def decode_func(self) -> str:
        return f"decode{self.name}"

    def object_type_name(self, raw_name: str) -> str:
        schema_type = self.name
        raw_type = to_dart_type_name(raw_name)
        return raw_type if raw_type.startswith(schema_type) else f"{schema_type}{raw_type}"

    def value_set_type_name(self, raw_name: str) -> str:
        return self.object_type_name(raw_name)


def unique_flutter_binary_schemas(schemas: list[BinarySchema | None]) -> list[FlutterBinarySchema]:
    result: list[FlutterBinarySchema] = []
    seen: set[str] = set()
    for schema in schemas:
        if schema is None:
            continue
        name = schema.name
        if name in seen:
            continue
        seen.add(name)
        result.append(FlutterBinarySchema(schema))
    return result
