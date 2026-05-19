from __future__ import annotations

import html
import inspect
import re
from collections import OrderedDict
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Any, Iterable, Mapping

from markdown_it import MarkdownIt


SUPPORTED_FIELD_TYPES = frozenset(
    {
        "u8",
        "u16",
        "u24",
        "u32",
        "u64",
        "i8",
        "i16",
        "i24",
        "i32",
        "i64",
        "f32",
        "f64",
        "bool",
        "bytes",
        "padding",
        "reserved",
        "string",
    }
)
INTEGER_FIELD_TYPES = frozenset({"u8", "u16", "u24", "u32", "u64", "i8", "i16", "i24", "i32", "i64"})
INTEGER_FIELD_BITS = {
    "u8": 8,
    "u16": 16,
    "u24": 24,
    "u32": 32,
    "u64": 64,
    "i8": 8,
    "i16": 16,
    "i24": 24,
    "i32": 32,
    "i64": 64,
}
SUPPORTED_RULE_KEYS = frozenset({"const", "min", "max", "sizeof", "assert", "layout", "encoding"})
SUPPORTED_BITFLAGS_RULE_KEYS = frozenset({"const", "enum"})
REQUIRED_TABLE_COLUMNS = ("field", "type", "count", "rule", "comment")
ENUM_VALUE_TABLE_COLUMNS = ("name", "value", "comment")
BITFLAGS_VALUE_TABLE_COLUMNS = frozenset(
    {
        ("name", "value", "comment"),
        ("name", "bit", "comment"),
        ("name", "bit", "rule", "comment"),
        ("name", "bits", "comment"),
        ("name", "bits", "rule", "comment"),
    }
)
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9_]*$")
VALUE_HEADING_RE = re.compile(r"^(enum|bitflags)\s+([A-Z][A-Za-z0-9_]*)\s*:\s*([A-Za-z0-9_]+)$")


class BinarySchemaError(ValueError):
    pass


@dataclass(frozen=True)
class BinaryField:
    name: str
    type: str
    count: str = "1"
    rule: Mapping[str, str] = dataclass_field(default_factory=dict)
    comment: str = ""

    @property
    def is_array(self) -> bool:
        return self.count not in {"", "1"}

    @property
    def is_dynamic_count(self) -> bool:
        return self.is_array and not self.count.isdigit()

    def to_manifest(self) -> dict[str, Any]:
        return {
            "field": self.name,
            "type": self.type,
            "count": self.count or "1",
            "rule": dict(self.rule),
            "comment": self.comment,
        }


@dataclass(frozen=True)
class BinaryObject:
    name: str
    fields: tuple[BinaryField, ...]
    kind: str = "struct"

    def field_map(self) -> dict[str, BinaryField]:
        return {field.name: field for field in self.fields}

    def to_manifest(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "fields": [field.to_manifest() for field in self.fields],
        }


@dataclass(frozen=True)
class BinarySection(BinaryObject):
    kind: str = "section"


@dataclass(frozen=True)
class BinaryValue:
    name: str
    value: str
    comment: str = ""
    bit: str | None = None
    bits: str | None = None
    rule: Mapping[str, str] = dataclass_field(default_factory=dict)

    @property
    def bit_range(self) -> tuple[int, int] | None:
        raw = self.bits if self.bits is not None else self.bit
        if raw is None:
            return None
        if ".." in raw:
            start_raw, end_raw = [part.strip() for part in raw.split("..", 1)]
        else:
            start_raw = raw.strip()
            end_raw = start_raw
        if not start_raw.isdigit() or not end_raw.isdigit():
            return None
        return int(start_raw), int(end_raw)

    @property
    def bit_start(self) -> int | None:
        bit_range = self.bit_range
        return bit_range[0] if bit_range is not None else None

    @property
    def bit_end(self) -> int | None:
        bit_range = self.bit_range
        return bit_range[1] if bit_range is not None else None

    @property
    def bit_width(self) -> int | None:
        bit_range = self.bit_range
        if bit_range is None:
            return None
        return bit_range[1] - bit_range[0] + 1

    @property
    def reserved_zero(self) -> bool:
        return self.rule.get("const") == "0"

    @property
    def enum_name(self) -> str | None:
        return self.rule.get("enum")

    def to_manifest(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "value": self.value,
            "comment": self.comment,
        }
        if self.bit is not None:
            payload["bit"] = self.bit
        if self.bits is not None:
            payload["bits"] = self.bits
        if self.bit_range is not None:
            payload["bit_start"] = self.bit_start
            payload["bit_end"] = self.bit_end
            payload["bit_width"] = self.bit_width
        if self.rule:
            payload["rule"] = dict(self.rule)
        return payload


@dataclass(frozen=True)
class BinaryValueSet:
    name: str
    base_type: str
    values: tuple[BinaryValue, ...]
    kind: str = "enum"

    def to_manifest(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "base_type": self.base_type,
            "kind": self.kind,
            "values": [value.to_manifest() for value in self.values],
        }
        if self.kind == "bitflags" and self.reserved_zero_mask:
            payload["reserved_zero_mask"] = self.reserved_zero_mask
        return payload

    @property
    def reserved_zero_mask(self) -> int:
        if self.kind != "bitflags":
            return 0
        mask = 0
        for value in self.values:
            if value.rule.get("const") != "0":
                continue
            parsed = _parse_int_literal(value.value)
            if parsed is not None:
                mask |= parsed
        return mask


@dataclass(frozen=True)
class BinarySchema:
    name: str
    endian: str
    content_type: str
    content_encoding: tuple[str, ...]
    sections: tuple[BinarySection, ...]
    structs: Mapping[str, BinaryObject]
    enums: Mapping[str, BinaryValueSet]
    bitflags: Mapping[str, BinaryValueSet]
    source_path: Path
    raw_markdown: str
    rendered_html: str

    def object_map(self) -> dict[str, BinaryObject]:
        objects = {section.name: section for section in self.sections}
        objects.update(self.structs)
        return objects

    def value_type_map(self) -> dict[str, BinaryValueSet]:
        values = dict(self.enums)
        values.update(self.bitflags)
        return values

    def to_manifest(self, *, include_html: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "source": self.source_path.as_posix(),
            "endian": self.endian,
            "content_type": self.content_type,
            "content_encoding": list(self.content_encoding),
            "sections": [section.to_manifest() for section in self.sections],
            "structs": [struct.to_manifest() for struct in self.structs.values()],
            "enums": [enum.to_manifest() for enum in self.enums.values()],
            "bitflags": [flags.to_manifest() for flags in self.bitflags.values()],
        }
        if include_html:
            payload["html"] = self.rendered_html
        return payload

    def to_route_manifest(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source_path.as_posix(),
            "endian": self.endian,
            "content_type": self.content_type,
            "content_encoding": list(self.content_encoding),
            "sections": [section.name for section in self.sections],
            "structs": list(self.structs),
            "enums": list(self.enums),
            "bitflags": list(self.bitflags),
            "html": self.rendered_html,
        }


def load_binary_schema(path: str | Path) -> BinarySchema:
    source_path = Path(path).resolve()
    if not source_path.is_file():
        raise BinarySchemaError(f"binary schema not found: {source_path}")
    return parse_binary_schema(source_path.read_text(encoding="utf-8"), source_path=source_path)


def resolve_schema_path(raw_path: str | Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path.resolve()
    caller = _first_external_caller()
    if caller is not None:
        candidate = (caller.parent / path).resolve()
        if candidate.exists():
            return candidate
    return path.resolve()


def parse_binary_schema(markdown: str, *, source_path: str | Path | None = None) -> BinarySchema:
    source = Path(source_path or "<memory>")
    parser = _markdown_parser()
    tokens = parser.parse(markdown)
    rendered_html = parser.render(markdown)

    headings = _collect_headings(tokens)
    h1 = [heading for heading in headings if heading[0] == 1]
    if len(h1) != 1:
        raise BinarySchemaError(f"{source}: binary schema must contain exactly one '# packet <Name>' heading")
    packet_name = _packet_name(h1[0][1], source)

    metadata = _parse_metadata(markdown, source)
    endian = metadata.get("endian", "little").strip().lower()
    if endian not in {"little", "big"}:
        raise BinarySchemaError(f"{source}: endian must be little or big")
    content_type = metadata.get("content-type", "application/octet-stream").strip()
    content_encoding = tuple(
        item.strip().lower()
        for item in metadata.get("content-encoding", "identity").split(",")
        if item.strip()
    )
    if not content_encoding:
        content_encoding = ("identity",)
    unsupported_encodings = sorted(set(content_encoding) - {"identity", "gzip"})
    if unsupported_encodings:
        raise BinarySchemaError(
            f"{source}: unsupported content-encoding: {', '.join(unsupported_encodings)}"
        )

    tables = _extract_schema_tables(tokens, source)
    sections: list[BinarySection] = []
    structs: "OrderedDict[str, BinaryObject]" = OrderedDict()
    enums: "OrderedDict[str, BinaryValueSet]" = OrderedDict()
    bitflags: "OrderedDict[str, BinaryValueSet]" = OrderedDict()
    for heading, rows in tables:
        if heading.startswith("struct "):
            fields = tuple(_fields_from_rows(rows, heading, source))
            name = heading.split(None, 1)[1].strip()
            _validate_type_name(name, source)
            if name in structs:
                raise BinarySchemaError(f"{source}: duplicate struct section: {name}")
            structs[name] = BinaryObject(name=name, fields=fields, kind="struct")
        elif value_heading := VALUE_HEADING_RE.fullmatch(heading):
            kind, name, base_type = value_heading.groups()
            _validate_type_name(name, source)
            if base_type not in INTEGER_FIELD_TYPES:
                raise BinarySchemaError(f"{source}: {heading} base type must be an integer field type")
            values = tuple(_values_from_rows(rows, heading, kind=kind, base_type=base_type, source=source))
            target = enums if kind == "enum" else bitflags
            if name in target:
                raise BinarySchemaError(f"{source}: duplicate {kind} section: {name}")
            target[name] = BinaryValueSet(name=name, base_type=base_type, values=values, kind=kind)
        else:
            fields = tuple(_fields_from_rows(rows, heading, source))
            section_name = _section_type_name(packet_name, heading)
            sections.append(BinarySection(name=section_name, fields=fields, kind="section"))

    if not sections:
        raise BinarySchemaError(f"{source}: packet must define at least one section table")

    schema = BinarySchema(
        name=packet_name,
        endian=endian,
        content_type=content_type,
        content_encoding=content_encoding,
        sections=tuple(sections),
        structs=structs,
        enums=enums,
        bitflags=bitflags,
        source_path=source.resolve() if source != Path("<memory>") else source,
        raw_markdown=markdown,
        rendered_html=rendered_html,
    )
    validate_binary_schema(schema)
    return schema


def validate_binary_schema(schema: BinarySchema) -> None:
    objects = schema.object_map()
    value_types = schema.value_type_map()
    packet_fields: dict[str, BinaryField] = {}
    for section in schema.sections:
        _validate_object(section, objects, value_types)
        for field in section.fields:
            if field.name in packet_fields:
                raise BinarySchemaError(f"{schema.source_path}: duplicate packet field: {field.name}")
            packet_fields[field.name] = field
    for struct in schema.structs.values():
        _validate_object(struct, objects, value_types)
    _validate_bitflags(schema)
    _validate_dynamic_bounds(schema, objects)


def schema_object_fields(schema: BinarySchema) -> Iterable[BinaryField]:
    for section in schema.sections:
        yield from section.fields
    for struct in schema.structs.values():
        yield from struct.fields


def _markdown_parser() -> MarkdownIt:
    return MarkdownIt("commonmark", {"html": False}).enable("table")


def _first_external_caller() -> Path | None:
    current = Path(__file__).resolve()
    for frame in inspect.stack()[2:]:
        filename = getattr(frame, "filename", "")
        if not filename:
            continue
        path = Path(filename).resolve()
        if path == current:
            continue
        if "api_blueprint/engine" in path.as_posix():
            continue
        return path
    return None


def _collect_headings(tokens: list[Any]) -> list[tuple[int, str]]:
    headings: list[tuple[int, str]] = []
    for index, token in enumerate(tokens):
        if token.type != "heading_open":
            continue
        try:
            level = int(str(token.tag).lstrip("h"))
        except ValueError:
            continue
        if index + 1 < len(tokens) and tokens[index + 1].type == "inline":
            headings.append((level, str(tokens[index + 1].content).strip()))
    return headings


def _packet_name(value: str, source: Path) -> str:
    parts = value.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "packet":
        raise BinarySchemaError(f"{source}: top heading must be '# packet <Name>'")
    name = parts[1].strip()
    _validate_type_name(name, source)
    return name


def _parse_metadata(markdown: str, source: Path) -> dict[str, str]:
    lines = markdown.splitlines()
    in_metadata = False
    in_fence = False
    metadata: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            in_metadata = True
            continue
        if not in_metadata:
            continue
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and stripped.startswith("## "):
            break
        if not stripped:
            continue
        if ":" not in stripped:
            raise BinarySchemaError(f"{source}: metadata line must be 'key: value': {stripped}")
        key, value = stripped.split(":", 1)
        metadata[key.strip().lower()] = value.strip()
    if in_fence:
        raise BinarySchemaError(f"{source}: metadata fence is not closed")
    return metadata


def _extract_schema_tables(tokens: list[Any], source: Path) -> list[tuple[str, list[list[str]]]]:
    current_h2: str | None = None
    tables: list[tuple[str, list[list[str]]]] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.type == "heading_open" and token.tag == "h2":
            current_h2 = ""
            if index + 1 < len(tokens) and tokens[index + 1].type == "inline":
                current_h2 = str(tokens[index + 1].content).strip()
            if not current_h2:
                raise BinarySchemaError(f"{source}: empty h2 heading")
        elif token.type == "table_open":
            if current_h2 is None:
                raise BinarySchemaError(f"{source}: schema table must follow a '##' heading")
            rows, index = _parse_table(tokens, index)
            tables.append((current_h2, rows))
        index += 1
    return tables


def _parse_table(tokens: list[Any], start: int) -> tuple[list[list[str]], int]:
    rows: list[list[str]] = []
    row: list[str] | None = None
    index = start + 1
    while index < len(tokens):
        token = tokens[index]
        if token.type == "table_close":
            return rows, index
        if token.type == "tr_open":
            row = []
        elif token.type == "tr_close":
            if row is not None:
                rows.append(row)
            row = None
        elif token.type in {"th_open", "td_open"} and row is not None:
            content = ""
            if index + 1 < len(tokens) and tokens[index + 1].type == "inline":
                content = str(tokens[index + 1].content).strip()
            row.append(html.unescape(content))
        index += 1
    return rows, index


def _fields_from_rows(rows: list[list[str]], heading: str, source: Path) -> list[BinaryField]:
    if not rows:
        raise BinarySchemaError(f"{source}: section[{heading}] table is empty")
    header = tuple(cell.strip().lower() for cell in rows[0])
    if header != REQUIRED_TABLE_COLUMNS:
        raise BinarySchemaError(
            f"{source}: section[{heading}] table columns must be: {', '.join(REQUIRED_TABLE_COLUMNS)}"
        )
    fields: list[BinaryField] = []
    for row in rows[1:]:
        padded = row + [""] * (len(REQUIRED_TABLE_COLUMNS) - len(row))
        field_name, field_type, count, rule_text, comment = [cell.strip() for cell in padded[:5]]
        if not field_name:
            raise BinarySchemaError(f"{source}: section[{heading}] has empty field name")
        if not IDENT_RE.fullmatch(field_name):
            raise BinarySchemaError(f"{source}: invalid field name: {field_name}")
        fields.append(
            BinaryField(
                name=field_name,
                type=field_type,
                count=count or "1",
                rule=_parse_rule(rule_text, source),
                comment=comment,
            )
        )
    return fields


def _values_from_rows(
    rows: list[list[str]],
    heading: str,
    *,
    kind: str,
    base_type: str,
    source: Path,
) -> list[BinaryValue]:
    if not rows:
        raise BinarySchemaError(f"{source}: section[{heading}] table is empty")
    header = tuple(cell.strip().lower() for cell in rows[0])
    if kind == "enum" and header != ENUM_VALUE_TABLE_COLUMNS:
        raise BinarySchemaError(
            f"{source}: section[{heading}] table columns must be: {', '.join(ENUM_VALUE_TABLE_COLUMNS)}"
        )
    if kind == "bitflags" and header not in BITFLAGS_VALUE_TABLE_COLUMNS:
        allowed = [
            ", ".join(columns)
            for columns in sorted(BITFLAGS_VALUE_TABLE_COLUMNS, key=lambda item: (len(item), item))
        ]
        raise BinarySchemaError(
            f"{source}: section[{heading}] table columns must be one of: {'; '.join(allowed)}"
        )

    values: list[BinaryValue] = []
    seen_names: set[str] = set()
    seen_values: set[str] = set()
    occupied_mask = 0
    for row in rows[1:]:
        padded = row + [""] * (len(header) - len(row))
        cells = {header[index]: cell.strip() for index, cell in enumerate(padded[: len(header)])}
        name = cells.get("name", "")
        value = cells.get("value", "")
        comment = cells.get("comment", "")
        bit = cells.get("bit")
        bits = cells.get("bits")
        rule = _parse_bitflags_rule(cells.get("rule", ""), source) if kind == "bitflags" else {}
        if not name:
            raise BinarySchemaError(f"{source}: section[{heading}] has empty value name")
        if not IDENT_RE.fullmatch(name):
            raise BinarySchemaError(f"{source}: invalid enum/bitflags value name: {name}")
        if kind == "bitflags" and (bit is not None or bits is not None):
            start, end = _parse_bit_range(bit if bit is not None else bits or "", source, heading, base_type)
            range_mask = _bit_range_mask(start, end)
            if occupied_mask & range_mask:
                raise BinarySchemaError(f"{source}: overlapping bitflags bits in {heading}: {name}")
            occupied_mask |= range_mask
            value = str(range_mask)
            bit = str(start) if bit is not None and start == end else None
            bits = str(start) if start == end else f"{start}..{end}"
        if not _is_valid_expr(value):
            raise BinarySchemaError(f"{source}: invalid enum/bitflags value: {value}")
        if name in seen_names:
            raise BinarySchemaError(f"{source}: duplicate enum/bitflags name in {heading}: {name}")
        if value in seen_values:
            raise BinarySchemaError(f"{source}: duplicate enum/bitflags value in {heading}: {value}")
        seen_names.add(name)
        seen_values.add(value)
        values.append(BinaryValue(name=name, value=value, comment=comment, bit=bit, bits=bits, rule=rule))
    return values


def _parse_rule(value: str, source: Path) -> Mapping[str, str]:
    if not value:
        return {}
    rules: dict[str, str] = {}
    for part in _split_rule_parts(value):
        if not part:
            continue
        if "=" not in part:
            raise BinarySchemaError(f"{source}: binary rule must be key=value: {part}")
        key, raw = part.split("=", 1)
        key = key.strip().lower()
        if key not in SUPPORTED_RULE_KEYS:
            raise BinarySchemaError(f"{source}: unsupported binary rule key: {key}")
        rules[key] = _strip_quotes(raw.strip())
    return rules


def _parse_bitflags_rule(value: str | None, source: Path) -> Mapping[str, str]:
    if not value:
        return {}
    rules: dict[str, str] = {}
    for part in _split_rule_parts(value):
        if not part:
            continue
        if "=" not in part:
            raise BinarySchemaError(f"{source}: bitflags rule must be key=value: {part}")
        key, raw = part.split("=", 1)
        key = key.strip().lower()
        if key not in SUPPORTED_BITFLAGS_RULE_KEYS:
            raise BinarySchemaError(f"{source}: unsupported bitflags rule key: {key}")
        rules[key] = _strip_quotes(raw.strip())
    return rules


def _split_rule_parts(value: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    for char in value:
        if char in {"'", '"'}:
            quote = None if quote == char else char if quote is None else quote
            buf.append(char)
            continue
        if char == "," and quote is None:
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(char)
    parts.append("".join(buf).strip())
    return parts


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _validate_type_name(name: str, source: Path) -> None:
    if not NAME_RE.fullmatch(name):
        raise BinarySchemaError(f"{source}: invalid binary type name: {name}")


def _section_type_name(packet_name: str, heading: str) -> str:
    return packet_name + "".join(part[:1].upper() + part[1:] for part in re.split(r"[^A-Za-z0-9]+", heading) if part)


def _validate_object(
    obj: BinaryObject,
    objects: Mapping[str, BinaryObject],
    value_types: Mapping[str, BinaryValueSet],
) -> None:
    seen: set[str] = set()
    for field in obj.fields:
        if field.name in seen:
            raise BinarySchemaError(f"duplicate field in {obj.name}: {field.name}")
        seen.add(field.name)
        if field.type not in SUPPORTED_FIELD_TYPES and field.type not in objects and field.type not in value_types:
            raise BinarySchemaError(f"{obj.name}.{field.name}: unsupported field type: {field.type}")
        if field.type in {"padding", "reserved"} and not field.count.isdigit():
            raise BinarySchemaError(f"{obj.name}.{field.name}: {field.type} count must be a fixed byte length")
        if field.count and not _is_valid_count(field.count):
            raise BinarySchemaError(f"{obj.name}.{field.name}: invalid count expression: {field.count}")
        field_is_integer = field.type in INTEGER_FIELD_TYPES or field.type in value_types
        for key, value in field.rule.items():
            if key in {"assert", "max", "min"} and not _is_valid_expr(value):
                raise BinarySchemaError(f"{obj.name}.{field.name}: invalid {key} expression: {value}")
            if key in {"assert", "min"} and not field_is_integer:
                raise BinarySchemaError(f"{obj.name}.{field.name}: {key} is only supported on integer fields")
            if key == "max" and not field_is_integer and not field.is_dynamic_count:
                raise BinarySchemaError(
                    f"{obj.name}.{field.name}: max is only supported on integer fields or dynamic counts"
                )
            if key == "sizeof" and not IDENT_RE.fullmatch(value):
                raise BinarySchemaError(f"{obj.name}.{field.name}: sizeof must reference a field name")


def _validate_bitflags(schema: BinarySchema) -> None:
    for flags in schema.bitflags.values():
        for value in flags.values:
            if const_value := value.rule.get("const"):
                if const_value != "0":
                    raise BinarySchemaError(
                        f"{schema.source_path}: bitflags {flags.name}.{value.name} only supports const=0"
                    )
            if enum_name := value.rule.get("enum"):
                if enum_name not in schema.enums:
                    raise BinarySchemaError(
                        f"{schema.source_path}: bitflags {flags.name}.{value.name} references unknown enum: {enum_name}"
                    )


def _validate_dynamic_bounds(schema: BinarySchema, objects: Mapping[str, BinaryObject]) -> None:
    for obj in objects.values():
        field_by_name = obj.field_map()
        if obj.kind == "section":
            packet_fields = {field.name: field for section in schema.sections for field in section.fields}
            field_by_name = {**packet_fields, **field_by_name}
        for field in obj.fields:
            if not field.is_dynamic_count:
                continue
            if "max" in field.rule:
                continue
            count_field = field_by_name.get(field.count)
            if count_field is not None and ("max" in count_field.rule or "assert" in count_field.rule):
                continue
            raise BinarySchemaError(
                f"{obj.name}.{field.name}: dynamic count[{field.count}] must have max on field or length field"
            )


def _is_valid_count(value: str) -> bool:
    return bool(value.isdigit() or IDENT_RE.fullmatch(value) or _is_valid_expr(value))


def _is_valid_expr(value: str) -> bool:
    value = value.strip()
    if not value:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_\s+\-*/()]+", value))


def _parse_bit_range(value: str, source: Path, heading: str, base_type: str) -> tuple[int, int]:
    raw = value.strip()
    if not raw:
        raise BinarySchemaError(f"{source}: empty bit range in {heading}")
    if ".." in raw:
        start_raw, end_raw = [part.strip() for part in raw.split("..", 1)]
    else:
        start_raw = raw
        end_raw = raw
    if not start_raw.isdigit() or not end_raw.isdigit():
        raise BinarySchemaError(f"{source}: bitflags bit range must use numeric bit indexes: {raw}")
    start = int(start_raw)
    end = int(end_raw)
    width = INTEGER_FIELD_BITS[base_type]
    if start > end:
        raise BinarySchemaError(f"{source}: bitflags bit range start must be <= end in {heading}: {raw}")
    if end >= width:
        raise BinarySchemaError(f"{source}: bitflags bit range exceeds {base_type} width in {heading}: {raw}")
    return start, end


def _bit_range_mask(start: int, end: int) -> int:
    return ((1 << (end - start + 1)) - 1) << start


def _parse_int_literal(value: str) -> int | None:
    try:
        return int(value, 0)
    except ValueError:
        return None
