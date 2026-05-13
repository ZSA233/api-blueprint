from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from api_blueprint.engine.binary_schema import BinaryField, BinaryObject, BinarySchema

from .naming import to_kotlin_property_name, to_kotlin_type_name


KOTLIN_SCALAR_TYPES = {
    "u8": "Int",
    "u16": "Int",
    "u24": "Int",
    "u32": "Long",
    "u64": "Long",
    "i8": "Int",
    "i16": "Int",
    "i24": "Int",
    "i32": "Int",
    "i64": "Long",
    "f32": "Float",
    "f64": "Double",
    "bool": "Boolean",
    "string": "String",
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
INTEGER_TYPES = {"u8", "u16", "u24", "u32", "u64", "i8", "i16", "i24", "i32", "i64"}
UNSIGNED_TYPES = {"u8", "u16", "u24", "u32", "u64"}
EXPR_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[()+\-*/]")


def kotlin_field_name(name: str) -> str:
    return to_kotlin_property_name(name)


def kotlin_type_name(name: str) -> str:
    return to_kotlin_type_name(name)


def kotlin_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def kotlin_byte_array_literal(value: str) -> str:
    items = ", ".join(str(byte) for byte in value.encode("utf-8"))
    return f"byteArrayOf({items})"


def kotlin_const_literal(field: "KotlinBinaryField") -> str:
    value = field.const_value
    if value is None:
        raise ValueError(f"{field.name} has no const rule")
    if field.is_bytes:
        return kotlin_byte_array_literal(value)
    if field.is_string:
        return kotlin_string(value)
    if field.typ in {"f32"}:
        return f"{value}f"
    if field.typ in {"f64"}:
        return value
    if field.typ == "bool":
        return "true" if value.lower() in {"true", "1"} else "false"
    if field.kotlin_type == "Long":
        return f"{value}L"
    return value


def compile_kotlin_long_expr(expr: str) -> str:
    tokens = EXPR_TOKEN_RE.findall(expr)
    compact = "".join(tokens)
    expected = re.sub(r"\s+", "", expr)
    if compact != expected or not tokens:
        raise ValueError(f"unsupported binary expression: {expr}")
    rendered: list[str] = []
    for token in tokens:
        if token.isdigit():
            rendered.append(f"{token}L")
        elif token in {"+", "-", "*", "/", "(", ")"}:
            rendered.append(token)
        else:
            rendered.append(f"state.{kotlin_field_name(token)}")
    return " ".join(rendered)


@dataclass(frozen=True)
class KotlinBinaryStateField:
    name: str

    @property
    def kotlin_name(self) -> str:
        return kotlin_field_name(self.name)


@dataclass(frozen=True)
class KotlinBinaryField:
    field: BinaryField
    schema: BinarySchema

    @property
    def name(self) -> str:
        return self.field.name

    @property
    def kotlin_name(self) -> str:
        return kotlin_field_name(self.field.name)

    @property
    def typ(self) -> str:
        return self.field.type

    @property
    def value_type(self):
        return self.schema.value_type_map().get(self.typ)

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
        return self.wire_type in KOTLIN_SCALAR_TYPES and self.wire_type != "string"

    @property
    def is_integer_scalar(self) -> bool:
        return self.wire_type in INTEGER_TYPES

    @property
    def is_unsigned(self) -> bool:
        return self.wire_type in UNSIGNED_TYPES

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
    def kotlin_type(self) -> str:
        if self.is_bytes:
            return "ByteArray"
        if self.is_string:
            return "String"
        if self.is_array:
            return f"List<{self.single_kotlin_type}>"
        return self.single_kotlin_type

    @property
    def single_kotlin_type(self) -> str:
        if self.value_type is not None:
            return KOTLIN_SCALAR_TYPES[self.wire_type]
        return KOTLIN_SCALAR_TYPES.get(self.typ, self.typ)

    @property
    def write_method(self) -> str:
        return WRITE_METHODS[self.wire_type]

    @property
    def supports_binary_block(self) -> bool:
        return self.is_array and not self.fixed_bytes

    @property
    def block_byte_size_expr(self) -> str | None:
        if self.is_bytes or self.is_string:
            return "block.count"
        if self.is_scalar:
            size = WIRE_SCALAR_SIZES.get(self.wire_type)
            if size is None:
                return None
            return f"block.count * {size}L"
        return None

    @property
    def has_dynamic_byte_string_param(self) -> bool:
        return self.is_bytes and not self.fixed_bytes

    @property
    def local_name(self) -> str:
        name = self.kotlin_name.replace("`", "")
        return name if name else "field"

    @property
    def count_var(self) -> str:
        return f"{self.local_name}Count"

    @property
    def max_count_var(self) -> str:
        return f"{self.local_name}MaxCount"

    @property
    def value_expr(self) -> str:
        return f"value.{self.kotlin_name}"

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
    def sizeof_kotlin_name(self) -> str | None:
        return kotlin_field_name(self.sizeof_value) if self.sizeof_value else None

    @property
    def default_expr(self) -> str | None:
        if self.const_value is None:
            return None
        return kotlin_const_literal(self)

    @property
    def const_long_expr(self) -> str:
        if self.const_value is None:
            raise ValueError(f"{self.name} has no const rule")
        return compile_kotlin_long_expr(self.const_value)

    @property
    def has_default(self) -> bool:
        return self.default_expr is not None

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
        return compile_kotlin_long_expr(self.count)

    @property
    def min_expr(self) -> str:
        if self.min_value is None:
            raise ValueError(f"{self.name} has no min rule")
        return compile_kotlin_long_expr(self.min_value)

    @property
    def max_expr(self) -> str:
        if self.max_value is None:
            raise ValueError(f"{self.name} has no max rule")
        return compile_kotlin_long_expr(self.max_value)

    @property
    def assert_expr(self) -> str:
        if self.assert_value is None:
            raise ValueError(f"{self.name} has no assert rule")
        return compile_kotlin_long_expr(self.assert_value)

    @property
    def value_long_expr(self) -> str:
        if self.kotlin_type == "Long":
            return self.value_expr
        if self.kotlin_type == "Int":
            return f"{self.value_expr}.toLong()"
        if self.kotlin_type == "Boolean":
            return f"if ({self.value_expr}) 1L else 0L"
        return self.value_expr

    @property
    def param_long_expr(self) -> str:
        if self.kotlin_type == "Long":
            return self.kotlin_name
        if self.kotlin_type == "Int":
            return f"{self.kotlin_name}.toLong()"
        if self.kotlin_type == "Boolean":
            return f"if ({self.kotlin_name}) 1L else 0L"
        return self.kotlin_name

    @property
    def param_declaration(self) -> str:
        default_expr = self.default_expr
        if default_expr is None:
            return f"{self.kotlin_name}: {self.kotlin_type}"
        return f"{self.kotlin_name}: {self.kotlin_type} = {default_expr}"

    @property
    def byte_string_param_declaration(self) -> str:
        if self.has_dynamic_byte_string_param:
            return f"{self.kotlin_name}: ByteString"
        return self.param_declaration


@dataclass(frozen=True)
class KotlinBinaryObject:
    obj: BinaryObject
    schema: BinarySchema

    @property
    def name(self) -> str:
        return self.obj.name

    @property
    def fields(self) -> list[KotlinBinaryField]:
        return [KotlinBinaryField(field, self.schema) for field in self.obj.fields]

    @property
    def data_fields(self) -> list[KotlinBinaryField]:
        fields = self.fields
        public_fields = [field for field in fields if not field.is_hidden]
        return [field for field in public_fields if not field.has_default] + [field for field in public_fields if field.has_default]

    @property
    def param_fields(self) -> list[KotlinBinaryField]:
        return self.data_fields

    @property
    def can_generate_param_writer(self) -> bool:
        return all(field.is_hidden or not (field.is_array and not field.is_bytes) for field in self.fields)

    @property
    def has_dynamic_bytes_param(self) -> bool:
        return any(field.has_dynamic_byte_string_param for field in self.fields)

    @property
    def writer_name(self) -> str:
        return "write" + kotlin_type_name(self.name)

    def block_factory_name(self, field: KotlinBinaryField) -> str:
        return "new" + kotlin_type_name(f"{self.name}_{field.name}_block")

    def block_writer_name(self, field: KotlinBinaryField) -> str:
        return "write" + kotlin_type_name(f"{self.name}_{field.name}_block")

    def fragment_writer_name(self, field: KotlinBinaryField) -> str:
        return "write" + kotlin_type_name(f"{self.name}_{field.name}_fragment")

    def block_path(self, field: KotlinBinaryField) -> str:
        return f"{self.name}.{field.name}"

    def has_field(self, name: str | None) -> bool:
        if name is None:
            return False
        return any(field.name == name and not field.is_hidden for field in self.fields)


@dataclass(frozen=True)
class KotlinBinaryValueSet:
    value_set: object

    @property
    def name(self) -> str:
        return self.value_set.name

    @property
    def kotlin_type(self) -> str:
        return KOTLIN_SCALAR_TYPES[self.value_set.base_type]

    @property
    def values(self):
        return self.value_set.values

    @property
    def values_object(self) -> str:
        return f"{self.name}Values"

    def value_name(self, name: str) -> str:
        return to_kotlin_type_name(name)

    def value_literal(self, value: str) -> str:
        if self.kotlin_type == "Long":
            return f"{value}L"
        return value


@dataclass(frozen=True)
class KotlinBinarySchema:
    schema: BinarySchema

    @property
    def name(self) -> str:
        return self.schema.name

    @property
    def endian(self) -> str:
        return "BinaryEndian.BIG" if self.schema.endian == "big" else "BinaryEndian.LITTLE"

    @property
    def content_type(self) -> str:
        return self.schema.content_type

    @property
    def sections(self) -> list[KotlinBinaryObject]:
        return [KotlinBinaryObject(section, self.schema) for section in self.schema.sections]

    @property
    def structs(self) -> list[KotlinBinaryObject]:
        return [KotlinBinaryObject(struct, self.schema) for struct in self.schema.structs.values()]

    @property
    def objects(self) -> list[KotlinBinaryObject]:
        return [*self.sections, *self.structs]

    @property
    def value_sets(self) -> list[KotlinBinaryValueSet]:
        values = [*self.schema.enums.values(), *self.schema.bitflags.values()]
        return [KotlinBinaryValueSet(value) for value in values]

    def packet_field_name(self, section_name: str) -> str:
        suffix = section_name.removeprefix(self.name)
        return kotlin_field_name(suffix or section_name)

    @property
    def state_type(self) -> str:
        return f"{self.name}BinaryState"

    @property
    def state_fields(self) -> list[KotlinBinaryStateField]:
        seen: set[str] = set()
        fields: list[KotlinBinaryStateField] = []
        for obj in self.objects:
            for field in obj.fields:
                if not field.can_store_var or field.name in seen:
                    continue
                seen.add(field.name)
                fields.append(KotlinBinaryStateField(field.name))
        return fields


def unique_kotlin_binary_schemas(schemas: Iterable[BinarySchema]) -> list[KotlinBinarySchema]:
    unique: dict[str, BinarySchema] = {}
    for schema in schemas:
        unique.setdefault(schema.name, schema)
    return [KotlinBinarySchema(schema) for schema in unique.values()]


def kotlin_binary_state_fields(schemas: Iterable[KotlinBinarySchema]) -> list[KotlinBinaryStateField]:
    seen: set[str] = set()
    fields: list[KotlinBinaryStateField] = []
    for schema in schemas:
        for field in schema.state_fields:
            if field.name in seen:
                continue
            seen.add(field.name)
            fields.append(field)
    return fields


def compact_kotlin_binary_source(source: str) -> str:
    lines = [line.rstrip() for line in source.splitlines()]
    compacted: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if compacted and compacted[-1] != "":
                compacted.append("")
            continue
        if stripped.startswith("package ") and compacted and compacted[-1].startswith("// Code generated"):
            compacted.append("")
        compacted.append(line)
    return "\n".join(compacted).strip() + "\n"
