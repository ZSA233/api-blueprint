from __future__ import annotations

from api_blueprint.writer.java.writer import JavaBaseWriter


class JavaServerWriter(JavaBaseWriter):
    target_label = "java-server"
    server_mode = True
