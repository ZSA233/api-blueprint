from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


class XMLResponse(JSONResponse):
    media_type = "application/xml"

    def render(self, content: Any) -> bytes:
        return content
