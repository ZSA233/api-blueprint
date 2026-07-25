from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping, Sequence

if TYPE_CHECKING:
    from api_blueprint.engine.router import Router
    from api_blueprint.writer.core.contracts import RouteContract


@dataclass(frozen=True)
class RouteDoc:
    summary: str
    description: str
    methods: tuple[str, ...]
    path: str
    route_id: str
    kind: str = "rpc"

    @classmethod
    def from_router(
        cls,
        router: "Router",
        contract: "RouteContract",
        *,
        fallback: str,
    ) -> "RouteDoc":
        extra = dict(getattr(router, "extra", {}) or {})
        description = _text(extra.get("description") or extra.get("desc"))
        summary = _text(extra.get("summary")) or _first_line(description) or fallback or contract.route_id
        kind = "stream" if contract.supports_stream else "channel" if contract.supports_channel else "rpc"
        return cls(
            summary=summary,
            description=description,
            methods=tuple(contract.http_methods),
            path=contract.url,
            route_id=contract.route_id,
            kind=kind,
        )

    @classmethod
    def from_manifest(cls, route: Mapping[str, object], *, fallback: str) -> "RouteDoc":
        description = _text(route.get("description"))
        summary = _text(route.get("summary")) or _first_line(description) or fallback or _text(route.get("id"))
        raw_methods = route.get("methods")
        methods = tuple(_text(method).upper() for method in raw_methods if _text(method)) if isinstance(raw_methods, list) else ()
        return cls(
            summary=summary,
            description=description,
            methods=methods,
            path=_text(route.get("url")),
            route_id=_text(route.get("id")),
            kind=_text(route.get("kind")) or "rpc",
        )

    def go_comment(self, *, subject: str, indent: str = "", include_route_id: bool = False) -> str:
        lines = self._lines(subject=subject, include_route_id=include_route_id)
        return "\n".join(_line_comment(line, prefix="//", indent=indent) for line in lines)

    def python_docstring(self, *, indent: str = "", include_route_id: bool = False) -> str:
        lines = [_escape_python_docstring(line) for line in self._lines(include_route_id=include_route_id)]
        if len(lines) == 1:
            return f'{indent}"""{lines[0]}"""'
        rendered = [f'{indent}"""{lines[0]}']
        rendered.extend(f"{indent}{line}" for line in lines[1:])
        rendered.append(f'{indent}"""')
        return "\n".join(rendered)

    def kdoc(self, *, indent: str = "", include_route_id: bool = False) -> str:
        return _block_comment(self._lines(include_route_id=include_route_id), indent=indent)

    def javadoc(self, *, indent: str = "", include_route_id: bool = False) -> str:
        return _block_comment(self._lines(include_route_id=include_route_id), indent=indent)

    def _lines(self, *, subject: str = "", include_route_id: bool = True) -> tuple[str, ...]:
        raw_summary = self.summary or _first_line(self.description) or self.route_id or self.path or "Route"
        summary = raw_summary
        if subject and summary and not summary.startswith(subject):
            summary = f"{subject}: {summary}"

        lines: list[str] = [summary]
        endpoint = " ".join(part for part in (self._methods_label(), self.path) if part)
        if endpoint:
            lines.append(endpoint)
        if include_route_id and self.route_id:
            lines.append(f"Route ID: {self.route_id}")
        return tuple(lines)

    def _methods_label(self) -> str:
        if self.methods:
            return ", ".join(self.methods)
        kind = self.kind.upper()
        return kind if kind and kind != "RPC" else "ROUTE"


def _text(value: object) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _first_line(value: str) -> str:
    for line in _normalized_lines(value):
        if line:
            return line
    return ""


def _normalized_lines(value: str) -> tuple[str, ...]:
    output: list[str] = []
    blank = False
    for raw_line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = " ".join(raw_line.strip().split())
        if not line:
            if output and not blank:
                output.append("")
            blank = True
            continue
        output.append(line)
        blank = False
    while output and output[-1] == "":
        output.pop()
    return tuple(output)


def _line_comment(line: str, *, prefix: str, indent: str) -> str:
    return f"{indent}{prefix}{' ' + line if line else ''}"


def _block_comment(lines: Sequence[str], *, indent: str) -> str:
    rendered = [f"{indent}/**"]
    rendered.extend(f"{indent} * {_escape_block_comment(line)}" if line else f"{indent} *" for line in lines)
    rendered.append(f"{indent} */")
    return "\n".join(rendered)


def _escape_block_comment(value: str) -> str:
    return value.replace("*/", "* /")


def _escape_python_docstring(value: str) -> str:
    return value.replace('"""', "'''")
