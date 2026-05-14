from __future__ import annotations

from api_blueprint.writer.java.writer import JavaBaseWriter


class JavaClientWriter(JavaBaseWriter):
    target_label = "java-client"
    client_mode = True
