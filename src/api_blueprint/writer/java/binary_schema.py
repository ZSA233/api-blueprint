from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .naming import to_java_constant_name, to_java_member_name, to_java_type_name


JsonObject = dict[str, Any]

JAVA_SCALAR_TYPES = {
    "u8": "Integer",
    "u16": "Integer",
    "u24": "Integer",
    "u32": "Long",
    "u64": "Long",
    "i8": "Integer",
    "i16": "Integer",
    "i24": "Integer",
    "i32": "Integer",
    "i64": "Long",
    "f32": "Float",
    "f64": "Double",
    "bool": "Boolean",
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


def _generated_name_key(value: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", value.lower())


def _java_string(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _scope_java_type_name(schema_name: str, raw_name: str) -> str:
    schema_type = to_java_type_name(schema_name, fallback="BinaryPacket")
    raw_type = to_java_type_name(raw_name, fallback="BinaryObject")
    return raw_type if raw_type.startswith(schema_type) else f"{schema_type}{raw_type}"


def _java_byte_array_literal(value: str) -> str:
    items = ", ".join(f"(byte) {item}" for item in value.encode("utf-8"))
    return f"new byte[] {{{items}}}"


def compile_java_long_expr(expr: str) -> str:
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
            rendered.append(f"state.{to_java_member_name(token)}")
    return " ".join(rendered)


@dataclass(frozen=True)
class JavaBinaryValue:
    raw: Mapping[str, Any]
    value_set: "JavaBinaryValueSet"

    @property
    def name(self) -> str:
        return str(self.raw.get("name") or "")

    @property
    def java_name(self) -> str:
        return to_java_constant_name(self.name, fallback="VALUE")

    @property
    def value(self) -> str:
        return str(self.raw.get("value") or "0")

    @property
    def literal(self) -> str:
        return f"{self.value}L" if self.value_set.java_type == "Long" else self.value


@dataclass(frozen=True)
class JavaBinaryValueSet:
    raw: Mapping[str, Any]
    schema: "JavaBinarySchema"

    @property
    def raw_name(self) -> str:
        return str(self.raw.get("name") or "")

    @property
    def name(self) -> str:
        return self.schema.value_set_type_name(self.raw_name)

    @property
    def kind(self) -> str:
        return str(self.raw.get("kind") or "enum")

    @property
    def base_type(self) -> str:
        return str(self.raw.get("base_type") or "u32")

    @property
    def java_type(self) -> str:
        return JAVA_SCALAR_TYPES[self.base_type]

    @property
    def values_class(self) -> str:
        return f"{self.name}Values"

    @property
    def values(self) -> tuple[JavaBinaryValue, ...]:
        raw_values = self.raw.get("values")
        if not isinstance(raw_values, list):
            return ()
        return tuple(JavaBinaryValue(value, self) for value in raw_values if isinstance(value, Mapping))

    @property
    def reserved_zero_mask(self) -> int:
        value = self.raw.get("reserved_zero_mask")
        return int(value) if isinstance(value, int) else 0


@dataclass(frozen=True)
class JavaBinaryStateField:
    name: str

    @property
    def java_name(self) -> str:
        return to_java_member_name(self.name)


@dataclass(frozen=True)
class JavaBinaryField:
    raw: Mapping[str, Any]
    schema: "JavaBinarySchema"

    @property
    def name(self) -> str:
        return str(self.raw.get("field") or self.raw.get("name") or "")

    @property
    def java_name(self) -> str:
        return to_java_member_name(self.name)

    @property
    def typ(self) -> str:
        return str(self.raw.get("type") or "bytes")

    @property
    def value_set(self) -> JavaBinaryValueSet | None:
        return self.schema.value_set_map.get(self.typ)

    @property
    def wire_type(self) -> str:
        value_set = self.value_set
        return value_set.base_type if value_set is not None else self.typ

    @property
    def count(self) -> str:
        return str(self.raw.get("count") or "1")

    @property
    def rule(self) -> Mapping[str, str]:
        value = self.raw.get("rule")
        return value if isinstance(value, Mapping) else {}

    @property
    def is_array(self) -> bool:
        return self.count != "1" and not self.is_bytes and not self.is_string and not self.is_hidden

    @property
    def is_scalar(self) -> bool:
        return self.wire_type in JAVA_SCALAR_TYPES and self.wire_type != "string"

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
    def is_public(self) -> bool:
        return not self.is_hidden and self.const_value is None

    @property
    def java_type(self) -> str:
        if self.is_bytes:
            return "byte[]"
        if self.is_string:
            return "String"
        if self.is_array:
            return f"List<{self.single_java_type}>"
        return self.single_java_type

    @property
    def single_java_type(self) -> str:
        value_set = self.value_set
        if value_set is not None:
            return value_set.java_type
        return JAVA_SCALAR_TYPES.get(self.typ, self.schema.object_type_name(self.typ))

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
    def count_expr(self) -> str:
        return compile_java_long_expr(self.count)

    @property
    def min_expr(self) -> str:
        return compile_java_long_expr(self.min_value or "0")

    @property
    def max_expr(self) -> str:
        return compile_java_long_expr(self.max_value or "0")

    @property
    def assert_expr(self) -> str:
        return compile_java_long_expr(self.assert_value or "0")

    @property
    def const_expr(self) -> str:
        if self.const_value is None:
            raise ValueError(f"{self.name} has no const rule")
        if self.is_bytes:
            return _java_byte_array_literal(self.const_value)
        if self.is_string:
            return _java_string(self.const_value)
        if self.wire_type == "bool":
            return "true" if self.const_value.lower() in {"true", "1"} else "false"
        if self.java_type in {"Long", "Double"}:
            suffix = "d" if self.java_type == "Double" else "L"
            return f"{self.const_value}{suffix}"
        if self.java_type == "Float":
            return f"{self.const_value}f"
        return self.const_value

    @property
    def const_long_expr(self) -> str:
        return compile_java_long_expr(self.const_value or "0")

    @property
    def value_expr(self) -> str:
        return self.const_expr if self.const_value is not None else f"value.{self.java_name}()"

    @property
    def value_long_expr(self) -> str:
        expr = self.value_expr
        if self.const_value is not None and self.is_integer_scalar:
            return self.const_long_expr
        if self.wire_type == "bool":
            return f"Boolean.TRUE.equals({expr}) ? 1L : 0L"
        if self.java_type in {"Integer", "Long", "Float", "Double"} or self.value_set is not None:
            return f"{expr}.longValue()"
        return expr

    @property
    def bitflags_zero_mask(self) -> int:
        value_set = self.value_set
        if value_set is None or value_set.kind != "bitflags":
            return 0
        return value_set.reserved_zero_mask

    @property
    def can_store_var(self) -> bool:
        return self.count == "1" and self.is_integer_scalar

    def check_encode_lines(self, receiver: str, long_expr: str) -> list[str]:
        lines: list[str] = []
        if self.const_value is not None:
            if self.is_bytes:
                lines.append(
                    f'GenBinaryRuntime.requireBinary("{self.name}", '
                    f"GenBinaryRuntime.bytesEqual({receiver}, {self.const_expr}), "
                    '"const mismatch");'
                )
            elif self.is_string:
                lines.append(
                    f'GenBinaryRuntime.requireBinary("{self.name}", '
                    f"java.util.Objects.equals({receiver}, {self.const_expr}), "
                    '"const mismatch");'
                )
            elif self.wire_type == "bool":
                lines.append(
                    f'GenBinaryRuntime.requireBinary("{self.name}", '
                    f"Boolean.TRUE.equals({receiver}) == {self.const_expr}, "
                    '"const mismatch");'
                )
            else:
                lines.append(
                    f'GenBinaryRuntime.requireBinary("{self.name}", {long_expr} == {self.const_long_expr}, '
                    '"const mismatch");'
                )
        if self.min_value is not None and self.is_integer_scalar:
            lines.append(f'GenBinaryRuntime.requireRange("{self.name}", {long_expr}, {self.min_expr}, Long.MAX_VALUE);')
        if self.max_value is not None and self.is_integer_scalar:
            lines.append(f'GenBinaryRuntime.requireRange("{self.name}", {long_expr}, Long.MIN_VALUE, {self.max_expr});')
        if self.assert_value is not None and self.is_integer_scalar:
            lines.append(f'GenBinaryRuntime.requireBinary("{self.name}", {long_expr} == {self.assert_expr}, "assert mismatch");')
        if self.bitflags_zero_mask:
            lines.append(
                f'GenBinaryRuntime.requireBinary("{self.name}", ({long_expr} & {self.bitflags_zero_mask}L) == 0L, '
                '"reserved bits must be zero");'
            )
        return lines

    def check_decode_lines(self, receiver: str, long_expr: str) -> list[str]:
        return [
            line.replace("requireBinary(", "requireDecodeBinary(").replace("requireRange(", "requireDecodeRange(")
            for line in self.check_encode_lines(receiver, long_expr)
        ]

    def render_write_lines(self, obj: "JavaBinaryObject") -> list[str]:
        lines: list[str] = []
        path = _java_string(self.name)
        if self.is_hidden:
            lines.append(f"writer.writeZeroes({path}, {self.count_expr});")
            return lines
        if self.is_bytes:
            receiver = self.value_expr
            if not self.fixed_bytes:
                lines.append(f"long {self.java_name}Count = {self.count_expr};")
                if self.max_value is not None:
                    lines.append(f"GenBinaryRuntime.requireRange({path}, {self.java_name}Count, 0L, {self.max_expr});")
                lines.append(f"GenBinaryRuntime.requireSize({path}, GenBinaryRuntime.binarySize({receiver}), {self.java_name}Count);")
                lines.extend(self.check_encode_lines(receiver, receiver))
                lines.append(f"writer.writeBytes({path}, {receiver});")
                return lines
            lines.extend(self.check_encode_lines(receiver, receiver))
            lines.append(f"GenBinaryRuntime.requireSize({path}, GenBinaryRuntime.binarySize({receiver}), {self.count_expr});")
            lines.append(f"writer.writeBytes({path}, {receiver});")
            return lines
        if self.is_string:
            receiver = self.value_expr
            lines.append(f"long {self.java_name}Count = {self.count_expr};")
            if self.max_value is not None:
                lines.append(f"GenBinaryRuntime.requireRange({path}, {self.java_name}Count, 0L, {self.max_expr});")
            lines.append(f"GenBinaryRuntime.requireSize({path}, GenBinaryRuntime.binarySize({receiver}), {self.java_name}Count);")
            lines.extend(self.check_encode_lines(receiver, receiver))
            lines.append(f"writer.writeUtf8String({path}, {receiver});")
            return lines
        if self.is_array:
            lines.append(f"long {self.java_name}Count = {self.count_expr};")
            if self.max_value is not None:
                lines.append(f"GenBinaryRuntime.requireRange({path}, {self.java_name}Count, 0L, {self.max_expr});")
            lines.append(f"GenBinaryRuntime.requireSize({path}, GenBinaryRuntime.binarySize({self.value_expr}), {self.java_name}Count);")
            lines.append(f"for (int index = 0; index < {self.value_expr}.size(); index++) {{")
            if self.is_scalar:
                lines.append("    try {")
                lines.append(f'        writer.{self.write_method}("", {self.value_expr}.get(index));')
                lines.append("    } catch (GenBinaryRuntime.BinaryEncodeException error) {")
                lines.append(f"        throw GenBinaryRuntime.wrapBinaryIndex({path}, index, error);")
                lines.append("    }")
            else:
                lines.append("    try {")
                lines.append(
                    f'        {self.schema.object_writer_name(self.typ)}({self.value_expr}.get(index), writer, state, "");'
                )
                lines.append("    } catch (GenBinaryRuntime.BinaryEncodeException error) {")
                lines.append(f"        throw GenBinaryRuntime.wrapBinaryIndex({path}, index, error);")
                lines.append("    }")
            lines.append("}")
            return lines
        if self.is_scalar:
            lines.extend(self.check_encode_lines(self.value_expr, self.value_long_expr))
            if self.sizeof_value and obj.has_public_field(self.sizeof_value):
                lines.append(
                    f'GenBinaryRuntime.requireSize("{self.name}.{self.sizeof_value}", '
                    f"GenBinaryRuntime.binarySize(value.{to_java_member_name(self.sizeof_value)}()), {self.value_long_expr});"
                )
            lines.append(f"writer.{self.write_method}({path}, {self.value_expr});")
            if self.can_store_var:
                lines.append(f"state.{self.java_name} = {self.value_long_expr};")
            return lines
        lines.append("try {")
        lines.append(f'    {self.schema.object_writer_name(self.typ)}({self.value_expr}, writer, state, "");')
        lines.append("} catch (GenBinaryRuntime.BinaryEncodeException error) {")
        lines.append(f"    throw GenBinaryRuntime.wrapBinaryField({path}, error);")
        lines.append("}")
        return lines

    def render_read_lines(self, obj: "JavaBinaryObject") -> list[str]:
        lines: list[str] = []
        path = _java_string(self.name)
        if self.is_hidden:
            lines.append(f"reader.readZeroes({path}, {self.count_expr});")
            return lines
        if self.is_bytes:
            count_expr = self.count_expr
            lines.append(f"byte[] {self.java_name} = reader.readBytes({path}, {count_expr});")
            lines.extend(self.check_decode_lines(self.java_name, "0L"))
            return lines
        if self.is_string:
            lines.append(f"String {self.java_name} = reader.readUtf8String({path}, {self.count_expr});")
            lines.extend(self.check_decode_lines(self.java_name, "0L"))
            return lines
        if self.is_array:
            lines.append(f"long {self.java_name}Count = {self.count_expr};")
            if self.max_value is not None:
                lines.append(f"GenBinaryRuntime.requireDecodeRange({path}, {self.java_name}Count, 0L, {self.max_expr});")
            lines.append(f"List<{self.single_java_type}> {self.java_name} = new ArrayList<>();")
            lines.append(f"for (int index = 0; index < {self.java_name}Count; index++) {{")
            if self.is_scalar:
                lines.append("    try {")
                lines.append(f'        {self.java_name}.add(reader.{self.read_method}(""));')
                lines.append("    } catch (GenBinaryRuntime.BinaryDecodeException error) {")
                lines.append(f"        throw GenBinaryRuntime.wrapBinaryIndex({path}, index, error);")
                lines.append("    }")
            else:
                lines.append("    try {")
                lines.append(f'        {self.java_name}.add({self.schema.object_reader_name(self.typ)}(reader, state, ""));')
                lines.append("    } catch (GenBinaryRuntime.BinaryDecodeException error) {")
                lines.append(f"        throw GenBinaryRuntime.wrapBinaryIndex({path}, index, error);")
                lines.append("    }")
            lines.append("}")
            return lines
        if self.is_scalar:
            lines.append(f"{self.java_type} {self.java_name} = reader.{self.read_method}({path});")
            if self.wire_type == "bool":
                long_expr = f"Boolean.TRUE.equals({self.java_name}) ? 1L : 0L"
            else:
                long_expr = f"{self.java_name}.longValue()"
            lines.extend(self.check_decode_lines(self.java_name, long_expr))
            if self.can_store_var:
                lines.append(f"state.{self.java_name} = {self.java_name}.longValue();")
            return lines
        lines.append(f"{self.single_java_type} {self.java_name};")
        lines.append("try {")
        lines.append(f'    {self.java_name} = {self.schema.object_reader_name(self.typ)}(reader, state, "");')
        lines.append("} catch (GenBinaryRuntime.BinaryDecodeException error) {")
        lines.append(f"    throw GenBinaryRuntime.wrapBinaryField({path}, error);")
        lines.append("}")
        return lines


@dataclass(frozen=True)
class JavaBinaryObject:
    raw: Mapping[str, Any]
    schema: "JavaBinarySchema"

    @property
    def raw_name(self) -> str:
        return str(self.raw.get("name") or "BinaryObject")

    @property
    def name(self) -> str:
        return self.schema.object_type_name(self.raw_name)

    @property
    def path_name(self) -> str:
        return self.raw_name

    @property
    def fields(self) -> tuple[JavaBinaryField, ...]:
        raw_fields = self.raw.get("fields")
        if not isinstance(raw_fields, list):
            return ()
        return tuple(JavaBinaryField(field, self.schema) for field in raw_fields if isinstance(field, Mapping))

    @property
    def data_fields(self) -> tuple[JavaBinaryField, ...]:
        return tuple(field for field in self.fields if field.is_public)

    @property
    def writer_name(self) -> str:
        return self.schema.object_writer_name(self.raw_name)

    @property
    def reader_name(self) -> str:
        return self.schema.object_reader_name(self.raw_name)

    def has_public_field(self, name: str | None) -> bool:
        return bool(name) and any(field.name == name and field.is_public for field in self.fields)


@dataclass(frozen=True)
class JavaBinarySchema:
    raw: Mapping[str, Any]

    @property
    def name(self) -> str:
        return to_java_type_name(str(self.raw.get("name") or "BinaryPacket"), fallback="BinaryPacket")

    @property
    def raw_name(self) -> str:
        return str(self.raw.get("name") or "BinaryPacket")

    @property
    def endian(self) -> str:
        return "GenBinaryRuntime.BinaryEndian.BIG" if str(self.raw.get("endian") or "little") == "big" else "GenBinaryRuntime.BinaryEndian.LITTLE"

    @property
    def content_type(self) -> str:
        return str(self.raw.get("content_type") or "application/octet-stream")

    @property
    def value_sets(self) -> tuple[JavaBinaryValueSet, ...]:
        values: list[JavaBinaryValueSet] = []
        for key in ("enums", "bitflags"):
            raw_sets = self.raw.get(key)
            if isinstance(raw_sets, list):
                values.extend(JavaBinaryValueSet(value, self) for value in raw_sets if isinstance(value, Mapping))
        return tuple(values)

    @property
    def value_set_map(self) -> dict[str, JavaBinaryValueSet]:
        return {value_set.raw_name: value_set for value_set in self.value_sets}

    @property
    def sections(self) -> tuple[JavaBinaryObject, ...]:
        raw_sections = self.raw.get("sections")
        if not isinstance(raw_sections, list):
            return ()
        return tuple(JavaBinaryObject(section, self) for section in raw_sections if isinstance(section, Mapping))

    @property
    def structs(self) -> tuple[JavaBinaryObject, ...]:
        raw_structs = self.raw.get("structs")
        if not isinstance(raw_structs, list):
            return ()
        return tuple(JavaBinaryObject(struct, self) for struct in raw_structs if isinstance(struct, Mapping))

    @property
    def objects(self) -> tuple[JavaBinaryObject, ...]:
        return (*self.sections, *self.structs)

    @property
    def state_type(self) -> str:
        return f"{self.name}BinaryState"

    @property
    def state_fields(self) -> tuple[JavaBinaryStateField, ...]:
        seen: set[str] = set()
        fields: list[JavaBinaryStateField] = []
        for obj in self.objects:
            for field in obj.fields:
                if not field.can_store_var or field.name in seen:
                    continue
                seen.add(field.name)
                fields.append(JavaBinaryStateField(field.name))
        return tuple(fields)

    def packet_field_name(self, section_name: str) -> str:
        suffix = section_name.removeprefix(self.name)
        return to_java_member_name(suffix or section_name)

    def object_type_name(self, object_name: str) -> str:
        return _scope_java_type_name(self.name, object_name)

    def value_set_type_name(self, value_set_name: str) -> str:
        return _scope_java_type_name(self.name, value_set_name)

    def object_writer_name(self, object_name: str) -> str:
        return to_java_member_name(f"write {self.object_type_name(object_name)}", fallback="writeBinaryObject")

    def object_reader_name(self, object_name: str) -> str:
        return to_java_member_name(f"read {self.object_type_name(object_name)}", fallback="readBinaryObject")


def unique_java_binary_schemas(schemas: Iterable[Mapping[str, Any]]) -> tuple[JavaBinarySchema, ...]:
    result: list[JavaBinarySchema] = []
    seen_raw: set[str] = set()
    seen_generated: dict[str, str] = {}
    for schema in schemas:
        name = str(schema.get("name") or "")
        if not name or name in seen_raw:
            continue
        generated_name = _generated_name_key(name)
        previous = seen_generated.get(generated_name)
        if previous is not None and previous != name:
            raise ValueError(f"duplicate binary schema generated name {to_java_type_name(name)}: {previous}, {name}")
        seen_raw.add(name)
        seen_generated[generated_name] = name
        result.append(JavaBinarySchema(schema))
    return tuple(result)
