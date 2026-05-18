from __future__ import annotations

from api_blueprint.writer.java.writer import JAVA_SERVER_GENERATED_HEADER, JavaBaseWriter


class JavaServerWriter(JavaBaseWriter):
    target_label = "java-server"
    server_mode = True
    generated_header = JAVA_SERVER_GENERATED_HEADER
