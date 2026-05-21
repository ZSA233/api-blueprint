from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable

from api_blueprint.engine.binary_schema import BinaryField, BinaryObject, BinarySchema


PY_SCALAR_TYPES = {
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
    "f32": "float",
    "f64": "float",
    "bool": "bool",
    "string": "str",
}
WRITE_METHODS = {
    "u8": "write_u8",
    "u16": "write_u16",
    "u24": "write_u24",
    "u32": "write_u32",
    "u64": "write_u64",
    "i8": "write_i8",
    "i16": "write_i16",
    "i24": "write_i24",
    "i32": "write_i32",
    "i64": "write_i64",
    "f32": "write_f32",
    "f64": "write_f64",
    "bool": "write_bool",
}
READ_METHODS = {
    "u8": "read_u8",
    "u16": "read_u16",
    "u24": "read_u24",
    "u32": "read_u32",
    "u64": "read_u64",
    "i8": "read_i8",
    "i16": "read_i16",
    "i24": "read_i24",
    "i32": "read_i32",
    "i64": "read_i64",
    "f32": "read_f32",
    "f64": "read_f64",
    "bool": "read_bool",
}
INTEGER_TYPES = {"u8", "u16", "u24", "u32", "u64", "i8", "i16", "i24", "i32", "i64"}
EXPR_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[()+\-*/]")


def py_name(value: str) -> str:
    name = re.sub(r"[^0-9A-Za-z_]+", "_", value).strip("_").lower()
    if not name:
        return "value"
    if name[0].isdigit():
        name = "value_" + name
    return name


def py_type_name(value: str) -> str:
    parts = [part for part in re.split(r"[^0-9A-Za-z_]+", value) if part]
    if not parts:
        return "Value"
    rendered = "".join(part[:1].upper() + part[1:] for part in parts)
    return f"Value{rendered}" if rendered[:1].isdigit() else rendered


def _scope_py_type_name(schema_name: str, raw_name: str) -> str:
    schema_type = py_type_name(schema_name)
    raw_type = py_type_name(raw_name)
    return raw_type if raw_type.startswith(schema_type) else f"{schema_type}{raw_type}"


def _packet_writer_name(packet_name: str) -> str:
    return f"write_{py_name(packet_name)}"


def _object_writer_name(packet_name: str, object_name: str) -> str:
    return f"{_packet_writer_name(packet_name)}_{py_name(object_name)}"


def _generated_name_key(value: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", value.lower())


def compile_py_int_expr(expr: str) -> str:
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
            rendered.append(f"state.get({json.dumps(py_name(token))}, 0)")
    return " ".join(rendered)


@dataclass(frozen=True)
class PythonBinaryField:
    field: BinaryField
    schema: "PythonBinarySchema"

    @property
    def name(self) -> str:
        return self.field.name

    @property
    def py_name(self) -> str:
        return py_name(self.field.name)

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
    def is_array(self) -> bool:
        return self.field.is_array

    @property
    def is_bytes(self) -> bool:
        return self.typ == "bytes"

    @property
    def is_string(self) -> bool:
        return self.typ == "string"

    @property
    def is_hidden(self) -> bool:
        return self.typ in {"padding", "reserved"}

    @property
    def is_scalar(self) -> bool:
        return self.wire_type in PY_SCALAR_TYPES and self.wire_type != "string"

    @property
    def is_integer_scalar(self) -> bool:
        return self.wire_type in INTEGER_TYPES

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
    def py_type(self) -> str:
        if self.is_bytes:
            return "bytes"
        if self.is_string:
            return "str"
        single = self.single_py_type
        if self.is_array:
            return f"list[{single}]"
        return single

    @property
    def single_py_type(self) -> str:
        if self.value_type is not None:
            return "int"
        return PY_SCALAR_TYPES.get(self.typ, self.schema.object_type_name(self.typ))

    @property
    def value_expr(self) -> str:
        if self.has_default:
            return self.const_expr
        return f"value.{self.py_name}"

    @property
    def const_expr(self) -> str:
        raw = self.rule.get("const", "0")
        if self.is_bytes:
            return repr(raw.encode("utf-8"))
        if self.is_string:
            return repr(raw)
        if self.wire_type == "bool":
            return "True" if raw.lower() in {"1", "true"} else "False"
        return raw

    @property
    def count_expr(self) -> str:
        return compile_py_int_expr(self.count)

    @property
    def min_expr(self) -> str:
        return compile_py_int_expr(self.rule.get("min", "0"))

    @property
    def max_expr(self) -> str:
        return compile_py_int_expr(self.rule.get("max", "0"))

    @property
    def assert_expr(self) -> str:
        return compile_py_int_expr(self.rule.get("assert", "0"))

    @property
    def write_method(self) -> str:
        return WRITE_METHODS[self.wire_type]

    @property
    def read_method(self) -> str:
        return READ_METHODS[self.wire_type]

    @property
    def sizeof_name(self) -> str | None:
        return self.rule.get("sizeof")

    @property
    def sizeof_py_name(self) -> str | None:
        return py_name(self.sizeof_name) if self.sizeof_name else None


@dataclass(frozen=True)
class PythonBinaryObject:
    obj: BinaryObject
    schema: "PythonBinarySchema"

    @property
    def name(self) -> str:
        return self.obj.name

    @property
    def py_type(self) -> str:
        return self.schema.object_type_name(self.obj.name)

    @property
    def path_name(self) -> str:
        return self.obj.name

    @property
    def writer_name(self) -> str:
        return self.schema.object_writer_name(self.obj.name)

    @property
    def reader_name(self) -> str:
        return self.schema.object_reader_name(self.obj.name)

    @property
    def fields(self) -> list[PythonBinaryField]:
        return [PythonBinaryField(field, self.schema) for field in self.obj.fields]

    @property
    def data_fields(self) -> list[PythonBinaryField]:
        return [field for field in self.fields if not field.is_hidden and not field.has_default]

    def has_public_field(self, name: str | None) -> bool:
        return bool(name) and any(
            field.name == name and not field.is_hidden and not field.has_default for field in self.fields
        )


@dataclass(frozen=True)
class PythonBinaryValueSet:
    value_set: object
    schema: "PythonBinarySchema"

    @property
    def name(self) -> str:
        return self.value_set.name

    @property
    def py_type(self) -> str:
        return self.schema.value_set_type_name(self.name)

    @property
    def values(self):
        return self.value_set.values

    def value_name(self, name: str) -> str:
        return py_type_name(name)


@dataclass(frozen=True)
class PythonBinarySchema:
    schema: BinarySchema

    @property
    def name(self) -> str:
        return self.schema.name

    @property
    def py_type(self) -> str:
        return py_type_name(self.schema.name)

    @property
    def endian(self) -> str:
        return self.schema.endian

    @property
    def content_type(self) -> str:
        return self.schema.content_type

    @property
    def sections(self) -> list[PythonBinaryObject]:
        return [PythonBinaryObject(section, self) for section in self.schema.sections]

    @property
    def structs(self) -> list[PythonBinaryObject]:
        return [PythonBinaryObject(struct, self) for struct in self.schema.structs.values()]

    @property
    def objects(self) -> list[PythonBinaryObject]:
        return [*self.sections, *self.structs]

    @property
    def value_sets(self) -> list[PythonBinaryValueSet]:
        values = [*self.schema.enums.values(), *self.schema.bitflags.values()]
        return [PythonBinaryValueSet(value, self) for value in values]

    @property
    def state_fields(self) -> list[str]:
        seen: set[str] = set()
        fields: list[str] = []
        for obj in self.objects:
            for field in obj.fields:
                if field.name in seen or field.count != "1" or not field.is_integer_scalar:
                    continue
                seen.add(field.name)
                fields.append(py_name(field.name))
        return fields

    def packet_field_name(self, section_name: str) -> str:
        suffix = section_name.removeprefix(self.name)
        return py_name(suffix or section_name)

    @property
    def writer_name(self) -> str:
        return _packet_writer_name(self.name)

    @property
    def reader_name(self) -> str:
        return f"parse_{py_name(self.name)}"

    def object_type_name(self, object_name: str) -> str:
        return _scope_py_type_name(self.name, object_name)

    def object_writer_name(self, object_name: str) -> str:
        return _object_writer_name(self.name, object_name)

    def object_reader_name(self, object_name: str) -> str:
        return f"read_{py_name(self.name)}_{py_name(object_name)}"

    def value_set_type_name(self, value_set_name: str) -> str:
        return _scope_py_type_name(self.name, value_set_name)


def unique_python_binary_schemas(schemas: Iterable[BinarySchema]) -> list[PythonBinarySchema]:
    unique: dict[str, BinarySchema] = {}
    generated_names: dict[str, str] = {}
    for schema in schemas:
        generated_name = _generated_name_key(schema.name)
        previous = generated_names.get(generated_name)
        if previous is not None and previous != schema.name:
            raise ValueError(f"duplicate binary schema generated name {py_type_name(schema.name)}: {previous}, {schema.name}")
        generated_names[generated_name] = schema.name
        unique.setdefault(schema.name, schema)
    return [PythonBinarySchema(schema) for schema in unique.values()]
