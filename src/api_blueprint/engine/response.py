import xml.etree.ElementTree as ET
import typing
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel




class XMLResponse(JSONResponse):
    media_type = "application/xml"

    def render(self, content: typing.Any) -> bytes:
        return content
