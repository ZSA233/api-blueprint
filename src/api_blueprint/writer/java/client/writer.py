from __future__ import annotations

from api_blueprint.writer.java.writer import JAVA_CLIENT_GENERATED_HEADER, JavaBaseWriter


class JavaClientWriter(JavaBaseWriter):
    target_label = "java-client"
    client_mode = True
    generated_header = JAVA_CLIENT_GENERATED_HEADER
