from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Iterable

from api_blueprint.engine.binary_schema import BinaryField, BinaryObject, BinarySchema, BinaryValueSet

from .naming import to_swift_identifier, to_swift_type_name


SWIFT_SCALAR_TYPES = {
    "u8": "Int",
    "u16": "Int",
    "u24": "Int",
    "u32": "Int",
    "u64": "UInt64",
    "i8": "Int",
    "i16": "Int",
    "i24": "Int",
    "i32": "Int",
    "i64": "Int64",
    "f32": "Float",
    "f64": "Double",
    "bool": "Bool",
    "string": "String",
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


def swift_binary_field_name(name: str) -> str:
    return to_swift_identifier(name, fallback="field")


def swift_binary_type_name(name: str) -> str:
    return to_swift_type_name(name, fallback="BinaryType")


def _scope_swift_type_name(schema_name: str, raw_name: str) -> str:
    schema_type = swift_binary_type_name(schema_name)
    raw_type = swift_binary_type_name(raw_name)
    return raw_type if raw_type.startswith(schema_type) else f"{schema_type}{raw_type}"


def _generated_name_key(value: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", value.lower())


def swift_string_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def swift_data_literal(value: str) -> str:
    return "Data([" + ", ".join(str(byte) for byte in value.encode("utf-8")) + "])"


def swift_const_literal(field: "SwiftBinaryField") -> str:
    value = field.const_value
    if value is None:
        raise ValueError(f"{field.name} has no const rule")
    if field.is_bytes:
        return swift_data_literal(value)
    if field.is_string:
        return swift_string_literal(value)
    if field.typ == "f32":
        return f"Float({value})"
    if field.typ == "f64":
        return value
    if field.typ == "bool":
        return "true" if value.lower() in {"true", "1"} else "false"
    if field.swift_type == "UInt64":
        return f"UInt64({value})"
    if field.swift_type == "Int64":
        return f"Int64({value})"
    return value


def compile_swift_int_expr(expr: str) -> str:
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
            rendered.append(f"state.{swift_binary_field_name(token)}")
    return " ".join(rendered)


@dataclass(frozen=True)
class SwiftBinaryStateField:
    name: str

    @property
    def swift_name(self) -> str:
        return swift_binary_field_name(self.name)


@dataclass(frozen=True)
class SwiftBinaryField:
    field: BinaryField
    schema: "SwiftBinarySchema"

    @property
    def name(self) -> str:
        return self.field.name

    @property
    def swift_name(self) -> str:
        return swift_binary_field_name(self.field.name)

    @property
    def typ(self) -> str:
        return self.field.type

    @property
    def value_type(self) -> BinaryValueSet | None:
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
        return self.wire_type in SWIFT_SCALAR_TYPES and self.wire_type != "string"

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
    def swift_type(self) -> str:
        if self.is_bytes:
            return "Data"
        if self.is_string:
            return "String"
        if self.is_array:
            return f"[{self.single_swift_type}]"
        return self.single_swift_type

    @property
    def single_swift_type(self) -> str:
        if self.value_type is not None:
            return SWIFT_SCALAR_TYPES[self.value_type.base_type]
        return SWIFT_SCALAR_TYPES.get(self.typ, self.schema.object_type_name(self.typ))

    @property
    def write_method(self) -> str:
        return WRITE_METHODS[self.wire_type]

    @property
    def read_method(self) -> str:
        return READ_METHODS[self.wire_type]

    @property
    def count_var(self) -> str:
        return f"{self.swift_name}Count"

    @property
    def value_expr(self) -> str:
        return f"value.{self.swift_name}"

    @property
    def write_value_expr(self) -> str:
        return self.default_expr or self.value_expr

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
    def sizeof_swift_name(self) -> str | None:
        return swift_binary_field_name(self.sizeof_value) if self.sizeof_value else None

    @property
    def default_expr(self) -> str | None:
        if self.const_value is None:
            return None
        return swift_const_literal(self)

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
        return compile_swift_int_expr(self.count)

    @property
    def const_long_expr(self) -> str:
        if self.const_value is None:
            raise ValueError(f"{self.name} has no const rule")
        return compile_swift_int_expr(self.const_value)

    @property
    def min_expr(self) -> str:
        if self.min_value is None:
            raise ValueError(f"{self.name} has no min rule")
        return compile_swift_int_expr(self.min_value)

    @property
    def max_expr(self) -> str:
        if self.max_value is None:
            raise ValueError(f"{self.name} has no max rule")
        return compile_swift_int_expr(self.max_value)

    @property
    def assert_expr(self) -> str:
        if self.assert_value is None:
            raise ValueError(f"{self.name} has no assert rule")
        return compile_swift_int_expr(self.assert_value)

    @property
    def write_int_expr(self) -> str:
        return self._int_expr(self.write_value_expr)

    @property
    def local_int_expr(self) -> str:
        return self._int_expr(self.swift_name)

    def _int_expr(self, expr: str) -> str:
        if self.swift_type == "Bool":
            return f"({expr} ? 1 : 0)"
        if self.swift_type in {"Int", "Int64", "UInt64"}:
            return f"Int({expr})"
        return expr


@dataclass(frozen=True)
class SwiftBinaryObject:
    obj: BinaryObject
    schema: "SwiftBinarySchema"

    @property
    def name(self) -> str:
        return self.schema.object_type_name(self.obj.name)

    @property
    def path_name(self) -> str:
        return self.obj.name

    @property
    def fields(self) -> list[SwiftBinaryField]:
        return [SwiftBinaryField(field, self.schema) for field in self.obj.fields]

    @property
    def data_fields(self) -> list[SwiftBinaryField]:
        return [field for field in self.fields if not field.is_hidden and not field.has_default]

    @property
    def writer_name(self) -> str:
        return "write" + swift_binary_type_name(self.name)

    @property
    def reader_name(self) -> str:
        return "read" + swift_binary_type_name(self.name)

    def has_field(self, name: str | None) -> bool:
        if name is None:
            return False
        return any(field.name == name and not field.is_hidden and not field.has_default for field in self.fields)


@dataclass(frozen=True)
class SwiftBinaryValueSet:
    value_set: BinaryValueSet
    schema: "SwiftBinarySchema"

    @property
    def name(self) -> str:
        return self.schema.value_set_type_name(self.value_set.name)

    @property
    def swift_type(self) -> str:
        return SWIFT_SCALAR_TYPES[self.value_set.base_type]

    @property
    def values(self):
        return self.value_set.values

    @property
    def values_object(self) -> str:
        return f"{self.name}Values"

    def value_name(self, name: str) -> str:
        return to_swift_identifier(name, fallback="value")

    def value_literal(self, value: str) -> str:
        if self.swift_type == "UInt64":
            return f"UInt64({value})"
        if self.swift_type == "Int64":
            return f"Int64({value})"
        return value


@dataclass(frozen=True)
class SwiftBinarySchema:
    schema: BinarySchema

    @property
    def name(self) -> str:
        return swift_binary_type_name(self.schema.name)

    @property
    def encode_func(self) -> str:
        return f"encode{self.name}"

    @property
    def decode_func(self) -> str:
        return f"decode{self.name}"

    @property
    def endian(self) -> str:
        return ".big" if self.schema.endian == "big" else ".little"

    @property
    def content_type(self) -> str:
        return self.schema.content_type

    @property
    def sections(self) -> list[SwiftBinaryObject]:
        return [SwiftBinaryObject(section, self) for section in self.schema.sections]

    @property
    def structs(self) -> list[SwiftBinaryObject]:
        return [SwiftBinaryObject(struct, self) for struct in self.schema.structs.values()]

    @property
    def objects(self) -> list[SwiftBinaryObject]:
        return [*self.sections, *self.structs]

    @property
    def value_sets(self) -> list[SwiftBinaryValueSet]:
        values = [*self.schema.enums.values(), *self.schema.bitflags.values()]
        return [SwiftBinaryValueSet(value, self) for value in values]

    @property
    def state_type(self) -> str:
        return f"{self.name}BinaryState"

    @property
    def state_fields(self) -> list[SwiftBinaryStateField]:
        seen: set[str] = set()
        fields: list[SwiftBinaryStateField] = []
        for obj in self.objects:
            for field in obj.fields:
                if not field.can_store_var or field.name in seen:
                    continue
                seen.add(field.name)
                fields.append(SwiftBinaryStateField(field.name))
        return fields

    def packet_field_name(self, section_name: str) -> str:
        suffix = section_name.removeprefix(self.name)
        return swift_binary_field_name(suffix or section_name)

    def object_type_name(self, object_name: str) -> str:
        return _scope_swift_type_name(self.name, object_name)

    def value_set_type_name(self, value_set_name: str) -> str:
        return _scope_swift_type_name(self.name, value_set_name)


def unique_swift_binary_schemas(schemas: Iterable[BinarySchema]) -> list[SwiftBinarySchema]:
    unique: dict[str, BinarySchema] = {}
    generated_names: dict[str, str] = {}
    for schema in schemas:
        generated_name = _generated_name_key(schema.name)
        previous = generated_names.get(generated_name)
        if previous is not None and previous != schema.name:
            raise ValueError(
                f"duplicate binary schema generated name {swift_binary_type_name(schema.name)}: "
                f"{previous}, {schema.name}"
            )
        generated_names[generated_name] = schema.name
        unique.setdefault(schema.name, schema)
    return [SwiftBinarySchema(schema) for schema in unique.values()]


def compact_swift_binary_source(source: str) -> str:
    lines = [line.rstrip() for line in source.splitlines()]
    compacted: list[str] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            previous_line = compacted[-1] if compacted else ""
            next_line = _next_nonblank_line(lines, index + 1)
            if _should_drop_swift_binary_blank(previous_line, next_line):
                continue
            if compacted and compacted[-1] != "":
                compacted.append("")
            continue
        compacted.append(line)
    return "\n".join(compacted).strip() + "\n"


def _next_nonblank_line(lines: list[str], start: int) -> str:
    for line in lines[start:]:
        if line.strip():
            return line
    return ""


def _swift_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _should_drop_swift_binary_blank(previous_line: str, next_line: str) -> bool:
    if not previous_line.strip() or not next_line.strip():
        return False
    previous = previous_line.strip()
    next_ = next_line.strip()
    if previous == "do {" or next_.startswith("} catch"):
        return True
    if previous.endswith("(") or next_ == ")":
        return True
    if previous == "}" and next_ == "}":
        return True
    return _swift_indent(previous_line) >= 12 and _swift_indent(next_line) >= 12
