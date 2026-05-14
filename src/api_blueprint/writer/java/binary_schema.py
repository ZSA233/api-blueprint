from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .naming import to_java_member_name, to_java_type_name


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class JavaBinaryField:
    raw: Mapping[str, Any]

    @property
    def name(self) -> str:
        return str(self.raw.get("field") or self.raw.get("name") or "")

    @property
    def java_name(self) -> str:
        return to_java_member_name(self.name)

    @property
    def java_type(self) -> str:
        typ = str(self.raw.get("type") or "bytes")
        if typ in {"bytes", "padding", "reserved"}:
            return "byte[]"
        if typ == "string":
            return "String"
        if typ in {"f32"}:
            return "Float"
        if typ in {"f64"}:
            return "Double"
        if typ in {"u32", "u64", "i64"}:
            return "Long"
        if typ in {"u8", "u16", "u24", "i8", "i16", "i24", "i32"}:
            return "Integer"
        if typ == "bool":
            return "Boolean"
        return "Object"

    @property
    def is_public(self) -> bool:
        return str(self.raw.get("type") or "") not in {"padding", "reserved"} and "const" not in self.rule

    @property
    def rule(self) -> Mapping[str, str]:
        value = self.raw.get("rule")
        return value if isinstance(value, Mapping) else {}


@dataclass(frozen=True)
class JavaBinaryObject:
    raw: Mapping[str, Any]

    @property
    def name(self) -> str:
        return to_java_type_name(str(self.raw.get("name") or "BinaryObject"))

    @property
    def fields(self) -> tuple[JavaBinaryField, ...]:
        raw_fields = self.raw.get("fields")
        if not isinstance(raw_fields, list):
            return ()
        return tuple(JavaBinaryField(field) for field in raw_fields if isinstance(field, Mapping))

    @property
    def public_fields(self) -> tuple[JavaBinaryField, ...]:
        return tuple(field for field in self.fields if field.is_public)


@dataclass(frozen=True)
class JavaBinarySchema:
    raw: Mapping[str, Any]

    @property
    def name(self) -> str:
        return to_java_type_name(str(self.raw.get("name") or "BinaryPacket"))

    @property
    def content_type(self) -> str:
        return str(self.raw.get("content_type") or "application/octet-stream")

    @property
    def sections(self) -> tuple[JavaBinaryObject, ...]:
        raw_sections = self.raw.get("sections")
        if not isinstance(raw_sections, list):
            return ()
        return tuple(JavaBinaryObject(section) for section in raw_sections if isinstance(section, Mapping))

    @property
    def structs(self) -> tuple[JavaBinaryObject, ...]:
        raw_structs = self.raw.get("structs")
        if not isinstance(raw_structs, list):
            return ()
        return tuple(JavaBinaryObject(struct) for struct in raw_structs if isinstance(struct, Mapping))

    @property
    def objects(self) -> tuple[JavaBinaryObject, ...]:
        return (*self.sections, *self.structs)


def unique_java_binary_schemas(schemas: list[Mapping[str, Any]]) -> tuple[JavaBinarySchema, ...]:
    result: list[JavaBinarySchema] = []
    seen: set[str] = set()
    for schema in schemas:
        name = str(schema.get("name") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(JavaBinarySchema(schema))
    return tuple(result)
