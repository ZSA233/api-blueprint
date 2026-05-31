from __future__ import annotations

import re


ROOTLESS_BLUEPRINT_NAME_REQUIRED_MESSAGE = (
    'rootless Blueprint requires explicit name; use Blueprint(name="api", root="") '
    'or Blueprint(name="legacy", root="")'
)


def normalize_blueprint_name(*, name: str | None, root: str) -> str:
    if name is not None:
        normalized_name = name.strip().strip("/")
        if not normalized_name:
            raise ValueError("Blueprint name must be non-empty when provided")
        return normalized_name

    normalized_root = root.strip().strip("/")
    if normalized_root:
        return normalized_root
    raise ValueError(ROOTLESS_BLUEPRINT_NAME_REQUIRED_MESSAGE)


def blueprint_root_slug(name: str) -> str:
    segments = [_slug_segment(segment) for segment in name.strip("/").split("/") if segment.strip()]
    slug = "_".join(segment for segment in segments if segment)
    if not slug:
        raise ValueError("Blueprint name must contain at least one alphanumeric character")
    return slug


def _slug_segment(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "_", value.lower()).strip("_")
