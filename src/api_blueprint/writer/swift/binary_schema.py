from __future__ import annotations

from dataclasses import dataclass

from api_blueprint.engine.binary_schema import BinarySchema

from .naming import to_swift_type_name


@dataclass(frozen=True)
class SwiftBinarySchema:
    schema: BinarySchema

    @property
    def name(self) -> str:
        return to_swift_type_name(self.schema.name, fallback="BinaryPacket")

    @property
    def encode_func(self) -> str:
        return f"encode{self.name}"

    @property
    def decode_func(self) -> str:
        return f"decode{self.name}"


def unique_swift_binary_schemas(schemas: list[BinarySchema]) -> list[SwiftBinarySchema]:
    result: list[SwiftBinarySchema] = []
    seen: set[str] = set()
    for schema in schemas:
        item = SwiftBinarySchema(schema)
        if item.name in seen:
            continue
        seen.add(item.name)
        result.append(item)
    return result
