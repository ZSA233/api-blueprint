from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from api_blueprint.engine.binary_schema import BinaryField, BinaryObject, BinarySchema
from api_blueprint.engine.utils import snake_to_pascal_case


GO_SCALAR_TYPES = {
    "u8": "uint8",
    "u16": "uint16",
    "u32": "uint32",
    "u64": "uint64",
    "i8": "int8",
    "i16": "int16",
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
    "u32": "ReadUint32",
    "u64": "ReadUint64",
    "i8": "ReadInt8",
    "i16": "ReadInt16",
    "i32": "ReadInt32",
    "i64": "ReadInt64",
    "f32": "ReadFloat32",
    "f64": "ReadFloat64",
    "bool": "ReadBool",
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
    "u32": 4,
    "u64": 8,
    "i8": 1,
    "i16": 2,
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


def go_byte_array_literal(value: str, count: str) -> str | None:
    if not count.isdigit():
        return None
    raw = value.encode("utf-8")
    if len(raw) != int(count):
        return None
    return f"[{count}]byte{{" + ", ".join(str(item) for item in raw) + "}"


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
        target = f"out.{field.go_name}"
        source = self.fixed_source
        if field.is_bytes:
            return f"copy({target}[:], {source})"
        if field.typ == "u8":
            return f"{target} = fixed[{self.offset}]"
        if field.typ == "i8":
            return f"{target} = int8(fixed[{self.offset}])"
        if field.typ == "bool":
            return f"{target} = fixed[{self.offset}] != 0"
        if field.typ == "u16":
            return f"{target} = reader.Order.Uint16({source})"
        if field.typ == "u32":
            return f"{target} = reader.Order.Uint32({source})"
        if field.typ == "u64":
            return f"{target} = reader.Order.Uint64({source})"
        if field.typ == "i16":
            return f"{target} = int16(reader.Order.Uint16({source}))"
        if field.typ == "i32":
            return f"{target} = int32(reader.Order.Uint32({source}))"
        if field.typ == "i64":
            return f"{target} = int64(reader.Order.Uint64({source}))"
        if field.typ == "f32":
            return f"{target} = binaryruntime.Float32(reader.Order, {source})"
        if field.typ == "f64":
            return f"{target} = binaryruntime.Float64(reader.Order, {source})"
        raise ValueError(f"unsupported fixed prefix field type: {field.typ}")


@dataclass(frozen=True)
class GoBinaryField:
    field: BinaryField
    schema: BinarySchema

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
        return self.typ in GO_SCALAR_TYPES and self.typ != "string"

    @property
    def is_integer_scalar(self) -> bool:
        return self.typ in {"u8", "u16", "u32", "u64", "i8", "i16", "i32", "i64"}

    @property
    def is_bytes(self) -> bool:
        return self.typ == "bytes"

    @property
    def is_string(self) -> bool:
        return self.typ == "string"

    @property
    def fixed_bytes(self) -> bool:
        return self.is_bytes and self.count.isdigit()

    @property
    def count_is_literal(self) -> bool:
        return self.count.isdigit()

    @property
    def go_type(self) -> str:
        if self.is_string:
            return "string"
        if self.fixed_bytes:
            return f"[{self.count}]byte"
        if self.is_array:
            return f"[]{self.single_go_type}"
        return self.single_go_type

    @property
    def single_go_type(self) -> str:
        if self.is_bytes:
            return "byte"
        return GO_SCALAR_TYPES.get(self.typ, self.typ)

    @property
    def read_method(self) -> str:
        return READ_METHODS[self.typ]

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
        return BULK_READ_METHODS[self.typ]

    @property
    def has_bulk_read_method(self) -> bool:
        return self.typ in BULK_READ_METHODS

    @property
    def fixed_wire_size(self) -> int:
        if self.fixed_bytes:
            return int(self.count)
        if self.count == "1" and self.typ in SCALAR_BYTE_SIZES:
            return SCALAR_BYTE_SIZES[self.typ]
        raise ValueError(f"{self.name} is not fixed-size")

    @property
    def can_join_fixed_prefix(self) -> bool:
        return self.fixed_bytes or (self.count == "1" and self.typ in SCALAR_BYTE_SIZES)

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
    def count_expr(self) -> str:
        return compile_go_binary_uint_expr(self.count)

    @property
    def min_expr(self) -> str:
        if self.min_value is None:
            raise ValueError(f"{self.name} has no min rule")
        return compile_go_binary_uint_expr(self.min_value)

    @property
    def max_expr(self) -> str:
        if self.max_value is None:
            raise ValueError(f"{self.name} has no max rule")
        return compile_go_binary_uint_expr(self.max_value)

    @property
    def assert_expr(self) -> str:
        if self.assert_value is None:
            raise ValueError(f"{self.name} has no assert rule")
        return compile_go_binary_uint_expr(self.assert_value)

    @property
    def const_expr(self) -> str:
        if self.const_value is None:
            raise ValueError(f"{self.name} has no const rule")
        return compile_go_binary_uint_expr(self.const_value)

    @property
    def fixed_bytes_const_literal(self) -> str | None:
        if self.const_value is None or not self.fixed_bytes:
            return None
        return go_byte_array_literal(self.const_value, self.count)

    @property
    def needs_math(self) -> bool:
        return self.typ in {"f32", "f64"}

    @property
    def needs_unsafe(self) -> bool:
        return (self.is_array and self.is_scalar and self.has_bulk_read_method) or self.is_string


@dataclass(frozen=True)
class GoBinaryObject:
    obj: BinaryObject
    schema: BinarySchema

    @property
    def name(self) -> str:
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
    def sections(self) -> list[GoBinaryObject]:
        return [GoBinaryObject(section, self.schema) for section in self.schema.sections]

    @property
    def structs(self) -> list[GoBinaryObject]:
        return [GoBinaryObject(struct, self.schema) for struct in self.schema.structs.values()]

    @property
    def objects(self) -> list[GoBinaryObject]:
        return [*self.sections, *self.structs]

    def packet_field_name(self, section_name: str) -> str:
        suffix = section_name.removeprefix(self.name)
        return suffix or section_name

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
    for schema in schemas:
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
