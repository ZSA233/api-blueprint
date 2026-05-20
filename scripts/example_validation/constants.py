from __future__ import annotations

import sys
from pathlib import Path
from typing import Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

GO_ENUM_VERSION = "v0.9.2"
KOTLIN_VERSION = "2.1.21"
KOTLINX_COROUTINES_VERSION = "1.10.2"
KOTLINX_SERIALIZATION_JSON_VERSION = "1.8.1"
OKHTTP_VERSION = "4.12.0"
OKIO_VERSION = "3.9.1"
KTOR_VERSION = "3.1.3"
JACKSON_DATABIND_VERSION = "2.17.2"
SPRING_BOOT_VERSION = "3.3.6"
GRADLE_BIN_ENV = "API_BLUEPRINT_GRADLE_BIN"
WAILS_V2_BIN_ENV = "API_BLUEPRINT_WAILS_V2_BIN"
WAILS_V3_BIN_ENV = "API_BLUEPRINT_WAILS_V3_BIN"

BLUEPRINT_GOLANG_SERVER_PRESERVED = (
    "go.mod",
    "go.sum",
    "main.go",
    "views/routes/api/binary/impl.go",
    "views/routes/api/conflict/impl.go",
    "views/routes/api/demo/assistant_session_error.go",
    "views/routes/api/demo/assistant_session_processor.go",
    "views/routes/api/demo/assistant_session_session.go",
    "views/routes/api/demo/impl.go",
    "views/routes/api/hello/impl.go",
    "views/routes/alt/conflict/impl.go",
)
BLUEPRINT_GOLANG_CLIENT_PRESERVED = (
    "go.mod",
    "go.sum",
)
BLUEPRINT_GOLANG_SUITE_PRESERVED = (
    "go.mod",
    "main.go",
)
BLUEPRINT_GOLANG_CONFORMANCE_PRESERVED = (
    "go.mod",
    "main.go",
)
BLUEPRINT_TYPESCRIPT_PRESERVED = (
    ".vscode/settings.json",
    "conformance.ts",
    "index.ts",
    "suite.ts",
    "tsconfig.json",
)
BLUEPRINT_KOTLIN_PRESERVED = ()
BLUEPRINT_KOTLIN_CLIENT_PRESERVED = ()
BLUEPRINT_KOTLIN_CONFORMANCE_PRESERVED = ("Conformance.kt",)
BLUEPRINT_JAVA_CLIENT_PRESERVED = (
    "com/example/apiblueprint/api/runtime/ApiClient.java",
    "com/example/apiblueprint/api/transports/http/HttpApiClient.java",
    "com/example/apiblueprint/api/routes/api/ApiApi.java",
    "com/example/apiblueprint/api/routes/api/binary/BinaryApi.java",
    "com/example/apiblueprint/api/routes/api/demo/DemoApi.java",
    "com/example/apiblueprint/api/routes/api/hello/HelloApi.java",
    "com/example/apiblueprint/static_/runtime/ApiClient.java",
    "com/example/apiblueprint/static_/transports/http/HttpApiClient.java",
    "com/example/apiblueprint/static_/routes/static_/StaticApi.java",
)
BLUEPRINT_JAVA_SERVER_PRESERVED = (
    "com/example/apiblueprint/api/routes/api/ApiService.java",
    "com/example/apiblueprint/api/routes/api/binary/BinaryService.java",
    "com/example/apiblueprint/api/routes/api/demo/DemoService.java",
    "com/example/apiblueprint/api/routes/api/hello/HelloService.java",
    "com/example/apiblueprint/static_/routes/static_/StaticService.java",
)
BLUEPRINT_JAVA_SUITE_PRESERVED = (
    ".gitignore",
    "build.gradle.kts",
    "settings.gradle.kts",
    "src/main/java/com/example/apiblueprint/suite/JavaExampleSuite.java",
)
BLUEPRINT_PYTHON_PRESERVED = ("client/suite.py",)
BLUEPRINT_FLUTTER_PRESERVED = (
    "pubspec.yaml",
    "analysis_options.yaml",
    "lib/src/api/runtime/api_client.dart",
    "lib/src/api/runtime/api_json_codecs.dart",
    "lib/src/api/transports/http/http_api_client.dart",
    "lib/src/api/routes/api/api_api.dart",
    "lib/src/api/routes/api/api_types.dart",
    "lib/src/api/routes/api/binary/binary.dart",
    "lib/src/api/routes/api/binary/binary_api.dart",
    "lib/src/api/routes/api/binary/binary_types.dart",
    "lib/src/api/routes/api/demo/demo_api.dart",
    "lib/src/api/routes/api/demo/demo_types.dart",
    "lib/src/api/routes/api/hello/hello_api.dart",
    "lib/src/api/routes/api/hello/hello_types.dart",
    "test/api_contract_test.dart",
    "test/binary_contract_test.dart",
    "test/conformance_test.dart",
    "test/http_transport_test.dart",
)
WAILS_HELLO_GOLANG_PRESERVED = (
    "go.mod",
    "go.sum",
    "routes/api/hello/impl.go",
)
WAILS_HELLO_TYPESCRIPT_PRESERVED = ("tsconfig.json",)
GRPC_GO_PRESERVED = ("go.mod", "go.sum")
GRPC_PYTHON_PRESERVED = ()
EXAMPLE_SNAPSHOT_IGNORES: Mapping[str, frozenset[str]] = {
    "blueprint/java/suite": frozenset((".gradle", "bin", "build")),
    "blueprint/flutter": frozenset((".dart_tool", "pubspec.lock")),
}
