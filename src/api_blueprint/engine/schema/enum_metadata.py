from __future__ import annotations

import ast
import enum
import inspect
import io
import textwrap
import tokenize
from dataclasses import dataclass
from functools import lru_cache
from typing import Any


@dataclass(frozen=True)
class EnumValueMetadata:
    name: str
    value: Any
    description: str | None = None


def enum_value_metadata(enum_cls: object) -> tuple[EnumValueMetadata, ...]:
    if not isinstance(enum_cls, enum.EnumMeta):
        return ()
    descriptions = enum_member_descriptions(enum_cls)
    return tuple(
        EnumValueMetadata(
            name=member.name,
            value=member.value,
            description=descriptions.get(member.name) or None,
        )
        for member in enum_cls
    )


def enum_schema_extensions(enum_cls: type[enum.Enum]) -> dict[str, list[str]]:
    values = enum_value_metadata(enum_cls)
    names = [value.name for value in values]
    extensions = {
        "x-enumNames": names,
        "x-enum-varnames": names,
    }
    descriptions = [value.description or "" for value in values]
    if any(descriptions):
        extensions["x-enumDescriptions"] = descriptions
        extensions["x-enum-descriptions"] = descriptions
    return extensions


def enum_comment_text(description: object, *, block_end: str | None = None) -> str:
    text = str(description or "").replace("\r", " ").replace("\n", " ").strip()
    while "  " in text:
        text = text.replace("  ", " ")
    if block_end:
        text = text.replace(block_end, block_end[:-1] + " " + block_end[-1:])
    return text


@lru_cache(maxsize=None)
def enum_member_descriptions(enum_cls: type[enum.Enum]) -> dict[str, str]:
    if not isinstance(enum_cls, enum.EnumMeta):
        return {}
    try:
        source = inspect.getsource(enum_cls)
    except (OSError, TypeError):
        return {}

    try:
        parsed = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return {}

    class_node = _first_class_def(parsed)
    if class_node is None:
        return {}

    comments = _line_comments(textwrap.dedent(source))
    assignments = _enum_member_assignment_lines(class_node, enum_cls)
    return {
        name: description
        for name, line_no in assignments.items()
        if (description := comments.get(line_no, "").strip())
    }


def _first_class_def(parsed: ast.Module) -> ast.ClassDef | None:
    for node in parsed.body:
        if isinstance(node, ast.ClassDef):
            return node
    return None


def _line_comments(source: str) -> dict[int, str]:
    result: dict[int, str] = {}
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type == tokenize.COMMENT:
                result[token.start[0]] = token.string.removeprefix("#").strip()
    except tokenize.TokenError:
        return {}
    return result


def _enum_member_assignment_lines(enum_node: ast.ClassDef, enum_cls: type[enum.Enum]) -> dict[str, int]:
    canonical_members = {member.name for member in enum_cls}
    result: dict[str, int] = {}
    for node in enum_node.body:
        for name in _assignment_target_names(node):
            if name in canonical_members:
                result[name] = node.lineno
    return result


def _assignment_target_names(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Assign):
        return tuple(target.id for target in node.targets if isinstance(target, ast.Name))
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return (node.target.id,)
    return ()
