from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from api_blueprint.engine.binary_schema import BinaryField, BinaryObject, BinarySchema

from .naming import to_camel


TS_SCALAR_TYPES = {
    "u8": "number",
    "u16": "number",
    "u24": "number",
    "u32": "number",
    "u64": "number",
    "i8": "number",
    "i16": "number",
    "i24": "number",
    "i32": "number",
    "i64": "number",
    "f32": "number",
    "f64": "number",
    "bool": "boolean",
    "string": "string",
}
WIRE_SCALAR_SIZES = {
    "u8": 1,
    "u16": 2,
    "u24": 3,
    "u32": 4,
    "u64": 8,
    "i8": 1,
    "i16": 2,
    "i24": 3,
    "i32": 4,
    "i64": 8,
    "f32": 4,
    "f64": 8,
    "bool": 1,
}
WRITE_METHODS = {
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
READ_METHODS = {
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
INTEGER_TYPES = {"u8", "u16", "u24", "u32", "u64", "i8", "i16", "i24", "i32", "i64"}
EXPR_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[()+\-*/]")


def ts_name(value: str) -> str:
    parts = [part for part in re.split(r"[^0-9A-Za-z_]+", value) if part]
    if not parts:
        return "Value"
    rendered = "".join(part[:1].upper() + part[1:] for part in parts)
    return f"Value{rendered}" if rendered[:1].isdigit() else rendered


def _scope_ts_name(schema_name: str, raw_name: str) -> str:
    schema_type = ts_name(schema_name)
    raw_type = ts_name(raw_name)
    return raw_type if raw_type.startswith(schema_type) else f"{schema_type}{raw_type}"


def _generated_name_key(value: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", value.lower())


def ts_field_name(value: str) -> str:
    return to_camel(value)


def ts_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def ts_bytes_literal(value: str) -> str:
    items = ", ".join(str(item) for item in value.encode("utf-8"))
    return f"new Uint8Array([{items}])"


def compile_ts_number_expr(expr: str) -> str:
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
            rendered.append(f"state.{ts_field_name(token)}")
    return " ".join(rendered)


@dataclass(frozen=True)
class TypeScriptBinaryField:
    field: BinaryField
    schema: "TypeScriptBinarySchema"

    @property
    def name(self) -> str:
        return self.field.name

    @property
    def ts_name(self) -> str:
        return ts_field_name(self.field.name)

    @property
    def typ(self) -> str:
        return self.field.type

    @property
    def value_type(self):
        return self.schema.schema.value_type_map().get(self.typ)

    @property
    def wire_type(self) -> str:
        value_type = self.value_type
        return value_type.base_type if value_type is not None else self.typ

    @property
    def count(self) -> str:
        return self.field.count

    @property
    def rule(self) -> dict[str, str]:
        return dict(self.field.rule)

    @property
    def is_array(self) -> bool:
        return self.field.is_array

    @property
    def is_scalar(self) -> bool:
        return self.wire_type in TS_SCALAR_TYPES and self.wire_type != "string"

    @property
    def is_integer_scalar(self) -> bool:
        return self.wire_type in INTEGER_TYPES

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
    def fixed_bytes(self) -> bool:
        return self.is_bytes and self.count.isdigit()

    @property
    def ts_type(self) -> str:
        if self.is_bytes:
            return "Uint8Array"
        if self.is_string:
            return "string"
        if self.is_array:
            return f"{self.single_ts_type}[]"
        if self.value_type is not None:
            return self.schema.value_set_type_name(self.typ)
        return self.single_ts_type

    @property
    def single_ts_type(self) -> str:
        if self.value_type is not None:
            return self.schema.value_set_type_name(self.typ)
        return TS_SCALAR_TYPES.get(self.typ, self.schema.object_type_name(self.typ))

    @property
    def write_method(self) -> str:
        return WRITE_METHODS[self.wire_type]

    @property
    def read_method(self) -> str:
        return READ_METHODS[self.wire_type]

    @property
    def supports_binary_block(self) -> bool:
        return self.is_array and not self.fixed_bytes and not self.is_hidden

    @property
    def block_byte_size_expr(self) -> str | None:
        if self.is_bytes or self.is_string:
            return "block.count"
        if self.is_scalar:
            size = WIRE_SCALAR_SIZES.get(self.wire_type)
            if size is None:
                return None
            return f"block.count * {size}"
        return None

    @property
    def count_expr(self) -> str:
        return compile_ts_number_expr(self.count)

    @property
    def const_value(self) -> str | None:
        return self.rule.get("const")

    @property
    def min_value(self) -> str | None:
        return self.rule.get("min")

    @property
    def max_value(self) -> str | None:
        return self.rule.get("max")

    @property
    def assert_value(self) -> str | None:
        return self.rule.get("assert")

    @property
    def sizeof_value(self) -> str | None:
        return self.rule.get("sizeof")

    @property
    def sizeof_ts_name(self) -> str | None:
        return ts_field_name(self.sizeof_value) if self.sizeof_value else None

    @property
    def default_expr(self) -> str | None:
        if self.const_value is None:
            return None
        if self.is_bytes:
            return ts_bytes_literal(self.const_value)
        if self.is_string:
            return ts_string(self.const_value)
        if self.wire_type == "bool":
            return "true" if self.const_value.lower() in {"true", "1"} else "false"
        return self.const_value

    @property
    def has_default(self) -> bool:
        return self.default_expr is not None

    @property
    def min_expr(self) -> str:
        return compile_ts_number_expr(self.min_value or "0")

    @property
    def max_expr(self) -> str:
        return compile_ts_number_expr(self.max_value or "0")

    @property
    def assert_expr(self) -> str:
        return compile_ts_number_expr(self.assert_value or "0")

    @property
    def const_expr(self) -> str:
        return compile_ts_number_expr(self.const_value or "0")

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
    def value_expr(self) -> str:
        if self.has_default and self.default_expr is not None:
            return self.default_expr
        return f"value.{self.ts_name}"


@dataclass(frozen=True)
class TypeScriptBinaryObject:
    obj: BinaryObject
    schema: "TypeScriptBinarySchema"

    @property
    def name(self) -> str:
        return self.schema.object_type_name(self.obj.name)

    @property
    def path_name(self) -> str:
        return self.obj.name

    @property
    def fields(self) -> list[TypeScriptBinaryField]:
        return [TypeScriptBinaryField(field, self.schema) for field in self.obj.fields]

    @property
    def data_fields(self) -> list[TypeScriptBinaryField]:
        return [field for field in self.fields if not field.is_hidden and not field.has_default]

    @property
    def writer_name(self) -> str:
        return "write" + ts_name(self.name)

    @property
    def reader_name(self) -> str:
        return "read" + ts_name(self.name)

    def block_factory_name(self, field: TypeScriptBinaryField) -> str:
        return "new" + ts_name(f"{self.name}_{field.name}_block")

    def block_writer_name(self, field: TypeScriptBinaryField) -> str:
        return "write" + ts_name(f"{self.name}_{field.name}_block")

    def fragment_writer_name(self, field: TypeScriptBinaryField) -> str:
        return "write" + ts_name(f"{self.name}_{field.name}_fragment")

    def block_path(self, field: TypeScriptBinaryField) -> str:
        return f"{self.path_name}.{field.name}"

    def has_field(self, name: str | None) -> bool:
        if name is None:
            return False
        return any(field.name == name and not field.is_hidden for field in self.fields)


@dataclass(frozen=True)
class TypeScriptBinaryValueSet:
    value_set: object
    schema: "TypeScriptBinarySchema"

    @property
    def name(self) -> str:
        return self.schema.value_set_type_name(self.value_set.name)

    @property
    def raw_name(self) -> str:
        return self.value_set.name

    @property
    def values_object(self) -> str:
        return f"{self.name}Values"

    @property
    def values(self):
        return self.value_set.values

    def value_name(self, name: str) -> str:
        return ts_name(name)


@dataclass(frozen=True)
class TypeScriptBinarySchema:
    schema: BinarySchema

    @property
    def name(self) -> str:
        return self.schema.name

    @property
    def endian(self) -> str:
        return '"big"' if self.schema.endian == "big" else '"little"'

    @property
    def content_type(self) -> str:
        return self.schema.content_type

    @property
    def sections(self) -> list[TypeScriptBinaryObject]:
        return [TypeScriptBinaryObject(section, self) for section in self.schema.sections]

    @property
    def structs(self) -> list[TypeScriptBinaryObject]:
        return [TypeScriptBinaryObject(struct, self) for struct in self.schema.structs.values()]

    @property
    def objects(self) -> list[TypeScriptBinaryObject]:
        return [*self.sections, *self.structs]

    @property
    def value_sets(self) -> list[TypeScriptBinaryValueSet]:
        values = [*self.schema.enums.values(), *self.schema.bitflags.values()]
        return [TypeScriptBinaryValueSet(value, self) for value in values]

    @property
    def state_type(self) -> str:
        return f"{self.name}BinaryState"

    @property
    def state_factory(self) -> str:
        return f"new{self.name}BinaryState"

    @property
    def reader_name(self) -> str:
        return f"parse{self.name}"

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
    def state_fields_ts(self) -> list[str]:
        return [ts_field_name(field) for field in self.state_fields]

    def packet_field_name(self, section_name: str) -> str:
        suffix = section_name.removeprefix(self.name)
        return ts_field_name(suffix or section_name)

    def object_type_name(self, object_name: str) -> str:
        return _scope_ts_name(self.name, object_name)

    def object_reader_name(self, object_name: str) -> str:
        return "read" + self.object_type_name(object_name)

    def value_set_type_name(self, value_set_name: str) -> str:
        return _scope_ts_name(self.name, value_set_name)


def unique_typescript_binary_schemas(schemas: Iterable[BinarySchema]) -> list[TypeScriptBinarySchema]:
    unique: dict[str, BinarySchema] = {}
    generated_names: dict[str, str] = {}
    for schema in schemas:
        generated_name = _generated_name_key(schema.name)
        previous = generated_names.get(generated_name)
        if previous is not None and previous != schema.name:
            raise ValueError(f"duplicate binary schema generated name {ts_name(schema.name)}: {previous}, {schema.name}")
        generated_names[generated_name] = schema.name
        unique.setdefault(schema.name, schema)
    return [TypeScriptBinarySchema(schema) for schema in unique.values()]
