from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Iterable

from api_blueprint.engine.binary_schema import BinaryField, BinaryObject, BinarySchema, BinaryValue, BinaryValueSet
from api_blueprint.engine.utils import snake_to_pascal_case


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
BULK_READ_METHODS = {
    "u8": "ReadUint8Array",
    "u16": "ReadUint16Array",
    "u32": "ReadUint32Array",
    "u64": "ReadUint64Array",
    "i8": "ReadInt8Array",
    "i16": "ReadInt16Array",
    "i32": "ReadInt32Array",
    "i64": "ReadInt64Array",
    "f32": "ReadFloat32Array",
    "f64": "ReadFloat64Array",
}
SCALAR_BYTE_SIZES = {
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
GO_INITIALISMS = {
    "id": "ID",
    "ts": "TS",
}
EXPR_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[()+\-*/]")


def binary_go_field_name(name: str) -> str:
    parts = [part for part in name.split("_") if part]
    if not parts:
        return snake_to_pascal_case(name, "", "Field")
    rendered = []
    for part in parts:
        lowered = part.lower()
        rendered.append(GO_INITIALISMS.get(lowered, part[:1].upper() + part[1:]))
    candidate = "".join(rendered)
    if not candidate or not candidate[0].isalpha():
        return snake_to_pascal_case(name, "", "Field")
    return candidate


def _scope_go_name(schema_name: str, raw_name: str) -> str:
    schema_type = binary_go_field_name(schema_name)
    raw_type = binary_go_field_name(raw_name)
    return raw_type if raw_type.startswith(schema_type) else f"{schema_type}{raw_type}"


def _unexported_go_name(name: str) -> str:
    return name[:1].lower() + name[1:] if name else "value"


def _generated_name_key(value: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", value.lower())


def compile_go_binary_uint_expr(expr: str) -> str:
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
            rendered.append(f"state.{binary_go_field_name(token)}")
    return " ".join(rendered)


def compile_go_binary_int_expr(expr: str) -> str:
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
            rendered.append(f"int64(state.{binary_go_field_name(token)})")
    return " ".join(rendered)


def go_byte_array_literal(value: str, count: str) -> str | None:
    if not count.isdigit():
        return None
    raw = value.encode("utf-8")
    if len(raw) != int(count):
        return None
    return f"[{count}]byte{{" + ", ".join(str(item) for item in raw) + "}"


def go_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


@dataclass(frozen=True)
class GoBinaryStateField:
    name: str

    @property
    def go_name(self) -> str:
        return binary_go_field_name(self.name)


@dataclass(frozen=True)
class GoBinaryFixedPrefixField:
    field: "GoBinaryField"
    offset: int

    @property
    def end(self) -> int:
        return self.offset + self.field.fixed_wire_size

    @property
    def fixed_source(self) -> str:
        return f"fixed[{self.offset}:{self.end}]"

    @property
    def assignment(self) -> str:
        field = self.field
        if field.is_hidden:
            return ""
        target = f"out.{field.go_name}"
        source = self.fixed_source
        cast = field.go_type if field.value_type is not None else ""

        def assign(expr: str) -> str:
            return f"{target} = {cast}({expr})" if cast else f"{target} = {expr}"

        if field.is_bytes:
            return f"copy({target}[:], {source})"
        if field.wire_type == "u8":
            return assign(f"fixed[{self.offset}]")
        if field.wire_type == "i8":
            return assign(f"int8(fixed[{self.offset}])")
        if field.wire_type == "bool":
            return assign(f"fixed[{self.offset}] != 0")
        if field.wire_type == "u16":
            return assign(f"reader.Order.Uint16({source})")
        if field.wire_type == "u24":
            return assign(f"binaryruntime.Uint24(reader.Order, {source})")
        if field.wire_type == "u32":
            return assign(f"reader.Order.Uint32({source})")
        if field.wire_type == "u64":
            return assign(f"reader.Order.Uint64({source})")
        if field.wire_type == "i16":
            return assign(f"int16(reader.Order.Uint16({source}))")
        if field.wire_type == "i24":
            return assign(f"binaryruntime.Int24(reader.Order, {source})")
        if field.wire_type == "i32":
            return assign(f"int32(reader.Order.Uint32({source}))")
        if field.wire_type == "i64":
            return assign(f"int64(reader.Order.Uint64({source}))")
        if field.wire_type == "f32":
            return assign(f"binaryruntime.Float32(reader.Order, {source})")
        if field.wire_type == "f64":
            return assign(f"binaryruntime.Float64(reader.Order, {source})")
        raise ValueError(f"unsupported fixed prefix field type: {field.typ}")


@dataclass(frozen=True)
class GoBinaryField:
    field: BinaryField
    schema: "GoBinarySchema"

    @property
    def name(self) -> str:
        return self.field.name

    @property
    def go_name(self) -> str:
        return binary_go_field_name(self.field.name)

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
        return self.wire_type in GO_SCALAR_TYPES and self.wire_type != "string"

    @property
    def is_integer_scalar(self) -> bool:
        return self.wire_type in {"u8", "u16", "u24", "u32", "u64", "i8", "i16", "i24", "i32", "i64"}

    @property
    def is_signed_integer_scalar(self) -> bool:
        return self.wire_type in {"i8", "i16", "i24", "i32", "i64"}

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
    def count_is_literal(self) -> bool:
        return self.count.isdigit()

    @property
    def go_type(self) -> str:
        if self.is_hidden:
            return ""
        if self.value_type is not None:
            return self.schema.value_set_type_name(self.typ)
        if self.is_string:
            return "string"
        if self.fixed_bytes:
            return f"[{self.count}]byte"
        if self.is_array:
            return f"[]{self.single_go_type}"
        return self.single_go_type

    @property
    def single_go_type(self) -> str:
        if self.value_type is not None:
            return self.schema.value_set_type_name(self.typ)
        if self.is_bytes:
            return "byte"
        return GO_SCALAR_TYPES.get(self.typ, self.schema.object_type_name(self.typ))

    @property
    def read_method(self) -> str:
        return READ_METHODS[self.wire_type]

    @property
    def write_method(self) -> str:
        return WRITE_METHODS[self.wire_type]

    @property
    def local_name(self) -> str:
        name = self.go_name
        return name[:1].lower() + name[1:] if name else "field"

    @property
    def count_var(self) -> str:
        return f"{self.local_name}Count"

    @property
    def max_count_var(self) -> str:
        return f"{self.local_name}MaxCount"

    @property
    def value_var(self) -> str:
        return f"{self.local_name}Value"

    @property
    def bulk_read_method(self) -> str:
        return BULK_READ_METHODS[self.wire_type]

    @property
    def has_bulk_read_method(self) -> bool:
        return self.value_type is None and self.wire_type in BULK_READ_METHODS

    @property
    def fixed_wire_size(self) -> int:
        if self.fixed_bytes:
            return int(self.count)
        if self.is_hidden and self.count.isdigit():
            return int(self.count)
        if self.count == "1" and self.wire_type in SCALAR_BYTE_SIZES:
            return SCALAR_BYTE_SIZES[self.wire_type]
        raise ValueError(f"{self.name} is not fixed-size")

    @property
    def can_join_fixed_prefix(self) -> bool:
        return self.fixed_bytes or (self.is_hidden and self.count.isdigit()) or (self.count == "1" and self.wire_type in SCALAR_BYTE_SIZES)

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
    def can_store_var(self) -> bool:
        return self.count == "1" and self.is_integer_scalar

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
    def count_expr(self) -> str:
        return compile_go_binary_uint_expr(self.count)

    @property
    def min_expr(self) -> str:
        if self.min_value is None:
            raise ValueError(f"{self.name} has no min rule")
        if self.is_signed_integer_scalar:
            return compile_go_binary_int_expr(self.min_value)
        return compile_go_binary_uint_expr(self.min_value)

    @property
    def max_expr(self) -> str:
        if self.max_value is None:
            raise ValueError(f"{self.name} has no max rule")
        if self.is_signed_integer_scalar:
            return compile_go_binary_int_expr(self.max_value)
        return compile_go_binary_uint_expr(self.max_value)

    @property
    def assert_expr(self) -> str:
        if self.assert_value is None:
            raise ValueError(f"{self.name} has no assert rule")
        if self.is_signed_integer_scalar:
            return compile_go_binary_int_expr(self.assert_value)
        return compile_go_binary_uint_expr(self.assert_value)

    @property
    def const_expr(self) -> str:
        if self.const_value is None:
            raise ValueError(f"{self.name} has no const rule")
        if self.is_signed_integer_scalar:
            return compile_go_binary_int_expr(self.const_value)
        return compile_go_binary_uint_expr(self.const_value)

    @property
    def fixed_bytes_const_literal(self) -> str | None:
        if self.const_value is None or not self.fixed_bytes:
            return None
        return go_byte_array_literal(self.const_value, self.count)

    @property
    def needs_math(self) -> bool:
        return self.wire_type in {"f32", "f64"}

    @property
    def needs_unsafe(self) -> bool:
        return (self.is_array and self.is_scalar and self.has_bulk_read_method) or self.is_string

    @property
    def scalar_assignment(self) -> str:
        if self.value_type is not None:
            return f"{self.go_type}({self.value_var})"
        return self.value_var

    @property
    def value_expr(self) -> str:
        return f"value.{self.go_name}"

    @property
    def numeric_value_expr(self) -> str:
        if self.wire_type == "bool":
            return self.value_expr
        if self.is_signed_integer_scalar:
            return f"int64({self.value_expr})"
        return f"uint64({self.value_expr})"

    @property
    def numeric_output_expr(self) -> str:
        if self.is_signed_integer_scalar:
            return f"int64(out.{self.go_name})"
        return f"uint64(out.{self.go_name})"

    def writer_expr(self, expr: str) -> str:
        if self.value_type is None:
            return expr
        return f"{GO_SCALAR_TYPES.get(self.wire_type, 'uint64')}({expr})"

    @property
    def write_const_expr(self) -> str:
        if self.const_value is None:
            raise ValueError(f"{self.name} has no const rule")
        if self.is_bytes:
            return f"[]byte({go_string(self.const_value)})"
        if self.is_string:
            return go_string(self.const_value)
        if self.wire_type == "bool":
            return "true" if self.const_value.lower() in {"1", "true"} else "false"
        if self.value_type is not None:
            return f"{self.go_type}({self.const_value})"
        return self.const_expr

    @property
    def sizeof_name(self) -> str | None:
        value = self.rule.get("sizeof")
        return str(value) if value else None

    @property
    def sizeof_go_name(self) -> str | None:
        return binary_go_field_name(self.sizeof_name) if self.sizeof_name else None


@dataclass(frozen=True)
class GoBinaryObject:
    obj: BinaryObject
    schema: "GoBinarySchema"

    @property
    def name(self) -> str:
        return self.schema.object_type_name(self.obj.name)

    @property
    def raw_name(self) -> str:
        return self.obj.name

    @property
    def fields(self) -> list[GoBinaryField]:
        return [GoBinaryField(field, self.schema) for field in self.obj.fields]

    @property
    def fixed_prefix_fields(self) -> list[GoBinaryFixedPrefixField]:
        fields: list[GoBinaryFixedPrefixField] = []
        offset = 0
        for field in self.fields:
            if not field.can_join_fixed_prefix:
                break
            fields.append(GoBinaryFixedPrefixField(field=field, offset=offset))
            offset += field.fixed_wire_size
        return fields

    @property
    def fixed_prefix_size(self) -> int:
        fields = self.fixed_prefix_fields
        if not fields:
            return 0
        return fields[-1].end

    @property
    def fixed_prefix_field_names(self) -> list[str]:
        return [field.field.name for field in self.fixed_prefix_fields]

    @property
    def dynamic_fields(self) -> list[GoBinaryField]:
        prefix_names = set(self.fixed_prefix_field_names)
        return [field for field in self.fields if field.name not in prefix_names]

    @property
    def has_fixed_prefix(self) -> bool:
        return bool(self.fixed_prefix_fields)

    @property
    def data_fields(self) -> list[GoBinaryField]:
        return [field for field in self.fields if not field.is_hidden]

    def has_public_field(self, name: str | None) -> bool:
        if not name:
            return False
        return any(field.name == name and not field.is_hidden for field in self.fields)


@dataclass(frozen=True)
class GoBinaryValue:
    value: BinaryValue
    value_set: "GoBinaryValueSet"

    @property
    def name(self) -> str:
        return self.value.name

    @property
    def value_literal(self) -> str:
        return self.value.value

    @property
    def bit_start(self) -> int:
        return self.value.bit_start or 0

    @property
    def bit_end(self) -> int:
        return self.value.bit_end or self.bit_start

    @property
    def bit_width(self) -> int:
        return self.bit_end - self.bit_start + 1

    @property
    def enum_name(self) -> str | None:
        return self.value_set.schema.value_set_type_name(self.value.enum_name) if self.value.enum_name else None

    @property
    def go_name(self) -> str:
        return binary_go_field_name(self.name)

    @property
    def is_reserved_zero(self) -> bool:
        return self.value.reserved_zero

    @property
    def is_single_bit_flag(self) -> bool:
        return (
            self.value_set.kind == "bitflags"
            and self.value.bit_range is not None
            and self.bit_start == self.bit_end
            and not self.is_reserved_zero
            and self.enum_name is None
        )

    @property
    def is_enum_bitfield(self) -> bool:
        return (
            self.value_set.kind == "bitflags"
            and self.value.bit_range is not None
            and not self.is_reserved_zero
            and self.enum_name is not None
        )


@dataclass(frozen=True)
class GoBinaryValueSet:
    value_set: BinaryValueSet
    schema: "GoBinarySchema"

    @property
    def name(self) -> str:
        return self.schema.value_set_type_name(self.value_set.name)

    @property
    def raw_name(self) -> str:
        return self.value_set.name

    @property
    def go_type(self) -> str:
        return GO_SCALAR_TYPES[self.value_set.base_type]

    @property
    def kind(self) -> str:
        return self.value_set.kind

    @property
    def values(self) -> list[GoBinaryValue]:
        return [GoBinaryValue(value, self) for value in self.value_set.values]

    @property
    def const_values(self) -> list[GoBinaryValue]:
        return [value for value in self.values if not value.is_reserved_zero]

    @property
    def single_bit_flags(self) -> list[GoBinaryValue]:
        return [value for value in self.values if value.is_single_bit_flag]

    @property
    def enum_bitfields(self) -> list[GoBinaryValue]:
        return [value for value in self.values if value.is_enum_bitfield]

    @property
    def reserved_zero_mask(self) -> int:
        return self.value_set.reserved_zero_mask

    @property
    def reserved_mask_name(self) -> str:
        return binary_go_field_name(f"{self.name}_reserved_mask")

    @property
    def has_helpers(self) -> bool:
        return self.kind == "bitflags" and (
            bool(self.single_bit_flags) or bool(self.enum_bitfields) or self.reserved_zero_mask != 0
        )

    def value_name(self, name: str) -> str:
        return binary_go_field_name(f"{self.name}_{name}")


@dataclass(frozen=True)
class GoBinarySchema:
    schema: BinarySchema

    @property
    def name(self) -> str:
        return self.schema.name

    @property
    def byte_order(self) -> str:
        return "stdbinary.BigEndian" if self.schema.endian == "big" else "stdbinary.LittleEndian"

    @property
    def runtime_byte_order(self) -> str:
        return "binaryruntime.BigEndian" if self.schema.endian == "big" else "binaryruntime.LittleEndian"

    @property
    def content_type(self) -> str:
        return self.schema.content_type or "application/octet-stream"

    @property
    def sections(self) -> list[GoBinaryObject]:
        return [GoBinaryObject(section, self) for section in self.schema.sections]

    @property
    def structs(self) -> list[GoBinaryObject]:
        return [GoBinaryObject(struct, self) for struct in self.schema.structs.values()]

    @property
    def objects(self) -> list[GoBinaryObject]:
        return [*self.sections, *self.structs]

    @property
    def value_sets(self) -> list[GoBinaryValueSet]:
        values = [*self.schema.enums.values(), *self.schema.bitflags.values()]
        return [GoBinaryValueSet(value, self) for value in values]

    def packet_field_name(self, section_name: str) -> str:
        suffix = section_name.removeprefix(self.name)
        return suffix or section_name

    @property
    def state_type(self) -> str:
        return f"{_unexported_go_name(binary_go_field_name(self.name))}BinaryState"

    def object_type_name(self, object_name: str) -> str:
        return _scope_go_name(self.name, object_name)

    def value_set_type_name(self, value_set_name: str) -> str:
        return _scope_go_name(self.name, value_set_name)

    @property
    def needs_math(self) -> bool:
        return any(field.needs_math for obj in self.objects for field in obj.fields)

    @property
    def needs_unsafe(self) -> bool:
        return any(field.needs_unsafe for obj in self.objects for field in obj.fields)

    @property
    def state_fields(self) -> list[GoBinaryStateField]:
        seen: set[str] = set()
        fields: list[GoBinaryStateField] = []
        for obj in self.objects:
            for field in obj.fields:
                if not field.can_store_var or field.name in seen:
                    continue
                seen.add(field.name)
                fields.append(GoBinaryStateField(field.name))
        return fields


def unique_go_binary_schemas(schemas: Iterable[BinarySchema]) -> list[GoBinarySchema]:
    unique: dict[str, BinarySchema] = {}
    generated_names: dict[str, str] = {}
    for schema in schemas:
        generated_name = _generated_name_key(schema.name)
        previous = generated_names.get(generated_name)
        if previous is not None and previous != schema.name:
            raise ValueError(
                f"duplicate binary schema generated name {binary_go_field_name(schema.name)}: "
                f"{previous}, {schema.name}"
            )
        generated_names[generated_name] = schema.name
        unique.setdefault(schema.name, schema)
    return [GoBinarySchema(schema) for schema in unique.values()]


def go_binary_state_fields(schemas: Iterable[GoBinarySchema]) -> list[GoBinaryStateField]:
    seen: set[str] = set()
    fields: list[GoBinaryStateField] = []
    for schema in schemas:
        for field in schema.state_fields:
            if field.name in seen:
                continue
            seen.add(field.name)
            fields.append(field)
    return fields


def compact_go_binary_source(source: str) -> str:
    lines = [line.rstrip() for line in source.splitlines()]
    compacted: list[str] = []
    in_import_block = False
    top_level_prefixes = (
        "import ",
        "var ",
        "const ",
        "type ",
        "func ",
    )
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_import_block and compacted and compacted[-1] != "" and compacted[-1].strip() != "import (":
                compacted.append("")
            continue
        if stripped.startswith("package ") and compacted and compacted[-1].startswith("// Code generated"):
            compacted.append("")
        is_top_level = not line.startswith("\t") and stripped.startswith(top_level_prefixes)
        if compacted and is_top_level and compacted[-1] != "":
            compacted.append("")
        compacted.append(line)
        if stripped == "import (":
            in_import_block = True
        elif in_import_block and stripped == ")":
            in_import_block = False
    return "\n".join(compacted).strip() + "\n"
