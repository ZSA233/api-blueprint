from __future__ import annotations

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
    return templates


def code_literal(value: Any) -> Markup:
    return Markup(json.dumps(value, ensure_ascii=False))


def _template_root(lang: str) -> Path:
    return Path(__file__).resolve().parents[1] / "templates" / lang


def render(lang: str, name: str, context: dict[str, Any], relative_path: str = "") -> str:
    templates = _TEMPLATE_CACHE.get(lang)
    if templates is None:
        path = _template_root(lang)
        templates = load_templates(str(path))
        _TEMPLATE_CACHE[lang] = templates
    return templates.get_template(str(Path(relative_path) / f"{name}.j2")).render(context)


def iter_render(
    lang: str,
    context: dict[str, Any],
    relative_path: str = "",
    exclusives: tuple[str, ...] = (),
):
    templates = _TEMPLATE_CACHE.get(lang)
    path = _template_root(lang)
    if templates is None:
        templates = load_templates(str(path))
        _TEMPLATE_CACHE[lang] = templates

    for file_name in os.listdir(path / relative_path.lstrip("/")):
        filepath = Path(file_name)
        filename = filepath.name
        orig_name, ext = os.path.splitext(filename)
        if ext not in [".j2", ".jinja"]:
            continue
        if orig_name in exclusives or orig_name.startswith("__"):
            continue
        yield orig_name, templates.get_template(str(Path(relative_path) / filename)).render(context)
