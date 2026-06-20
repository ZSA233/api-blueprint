from __future__ import annotations

from collections.abc import Iterator
import json
import os
from pathlib import Path
from typing import Any

from fastapi.templating import Jinja2Templates
from markupsafe import Markup


_TEMPLATE_CACHE: dict[str, Jinja2Templates] = {}


def load_templates(directory: str | None) -> Jinja2Templates:
    templates = Jinja2Templates(directory=directory)
    templates.env.filters["code_literal"] = code_literal
    templates.env.filters["compact_code_block"] = compact_code_block
    return templates


def code_literal(value: Any) -> Markup:
    return Markup(json.dumps(value, ensure_ascii=False))


def compact_code_block(value: Any) -> Markup:
    lines = [line.strip() for line in str(value).splitlines() if line.strip()]
    return Markup("\n".join(lines))


def _template_root(lang: str) -> Path:
    return Path(__file__).resolve().parents[1] / "templates" / lang


def _template_relative_parts(relative_path: str) -> tuple[str, ...]:
    normalized = relative_path.replace("\\", "/")
    return tuple(part for part in normalized.split("/") if part and part != ".")


def _template_lookup_name(relative_path: str, name: str) -> str:
    return "/".join((*_template_relative_parts(relative_path), name))


def render(lang: str, name: str, context: dict[str, Any], relative_path: str = "") -> str:
    templates = _TEMPLATE_CACHE.get(lang)
    if templates is None:
        path = _template_root(lang)
        templates = load_templates(str(path))
        _TEMPLATE_CACHE[lang] = templates
    text = templates.get_template(_template_lookup_name(relative_path, f"{name}.j2")).render(context)
    return normalize_generated_source(lang, text)


def iter_render(
    lang: str,
    context: dict[str, Any],
    relative_path: str = "",
    exclusives: tuple[str, ...] = (),
) -> Iterator[tuple[str, str]]:
    templates = _TEMPLATE_CACHE.get(lang)
    path = _template_root(lang)
    if templates is None:
        templates = load_templates(str(path))
        _TEMPLATE_CACHE[lang] = templates

    relative_parts = _template_relative_parts(relative_path)
    for file_name in os.listdir(path.joinpath(*relative_parts)):
        filepath = Path(file_name)
        filename = filepath.name
        orig_name, ext = os.path.splitext(filename)
        if ext not in [".j2", ".jinja"]:
            continue
        if orig_name in exclusives or orig_name.startswith("__"):
            continue
        text = templates.get_template(_template_lookup_name(relative_path, filename)).render(context)
        yield orig_name, normalize_generated_source(lang, text)


def normalize_generated_source(lang: str, text: str) -> str:
    if lang not in {"flutter", "golang", "java", "kotlin", "swift", "typescript"}:
        return text
    return _strip_trailing_blank_lines(_collapse_blank_line_runs(text, max_blank_lines=1))


def _strip_trailing_blank_lines(text: str) -> str:
    stripped = text.rstrip()
    if not stripped:
        return ""
    return stripped + "\n"


def _collapse_blank_line_runs(text: str, *, max_blank_lines: int) -> str:
    trailing_newline = text.endswith("\n")
    lines: list[str] = []
    blank_count = 0
    for line in text.splitlines():
        if line.strip():
            blank_count = 0
            lines.append(line)
            continue
        blank_count += 1
        if blank_count <= max_blank_lines:
            lines.append("")
    result = "\n".join(lines)
    if trailing_newline:
        result += "\n"
    return result
