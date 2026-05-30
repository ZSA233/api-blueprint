from __future__ import annotations

from .helpers import *


def test_preserved_harnesses_dispatch_expanded_scenarios() -> None:
    root = REPO_ROOT
    expected = (
        "raw",
        "xml",
        "static",
        "header",
        "scalar",
        "enum",
        "map",
        "deprecated",
        "audit-binary",
        "single-channel",
    )
    expected_without_websocket = tuple(name for name in expected if name != "single-channel")

    harnesses = [
        (root / "examples/golang/conformance/main.go", expected),
        (root / "examples/typescript/conformance.ts", expected),
        (root / "examples/kotlin/conformance/Conformance.kt", expected),
        (root / "examples/flutter/test/conformance_test.dart", expected),
        (root / "examples/swift/Conformance/Sources/SwiftConformance/main.swift", expected_without_websocket),
        (root / "examples/java/conformance/Conformance.java", expected),
        (root / "examples/python/conformance/client.py", expected),
    ]
    for harness, names in harnesses:
        text = harness.read_text(encoding="utf-8")
        missing = [name for name in names if name not in text]
        assert not missing, f"{harness} missing scenarios: {missing}"

def test_prepare_blueprint_outputs_preserves_kotlin_conformance_source(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    conformance_file = source_root / "kotlin" / "conformance" / "Conformance.kt"
    conformance_file.parent.mkdir(parents=True)
    conformance_file.write_text("package com.example.apiblueprint.conformance\n", encoding="utf-8")

    example_validation._prepare_blueprint_outputs(source_root=source_root, target_root=target_root)

    assert (target_root / "kotlin" / "conformance" / "Conformance.kt").read_text(encoding="utf-8") == (
        "package com.example.apiblueprint.conformance\n"
    )

def test_prepare_blueprint_outputs_preserves_java_python_conformance_sources(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    java_file = source_root / "java" / "conformance" / "Conformance.java"
    python_file = source_root / "python" / "conformance" / "client.py"
    java_file.parent.mkdir(parents=True)
    python_file.parent.mkdir(parents=True)
    java_file.write_text("package com.example.apiblueprint.conformance;\n", encoding="utf-8")
    python_file.write_text("print('python conformance')\n", encoding="utf-8")

    example_validation._prepare_blueprint_outputs(source_root=source_root, target_root=target_root)

    assert (target_root / "java" / "conformance" / "Conformance.java").read_text(encoding="utf-8") == (
        "package com.example.apiblueprint.conformance;\n"
    )
    assert (target_root / "python" / "conformance" / "client.py").read_text(encoding="utf-8") == (
        "print('python conformance')\n"
    )

def test_prepare_blueprint_outputs_preserves_swift_conformance_sources(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    package_file = source_root / "swift" / "Conformance" / "Package.swift"
    source_file = source_root / "swift" / "Conformance" / "Sources" / "SwiftConformance" / "main.swift"
    source_file.parent.mkdir(parents=True)
    package_file.parent.mkdir(parents=True, exist_ok=True)
    package_file.write_text("// swift-tools-version: 5.9\n", encoding="utf-8")
    source_file.write_text("print(\"swift conformance\")\n", encoding="utf-8")

    example_validation._prepare_blueprint_outputs(source_root=source_root, target_root=target_root)

    assert (target_root / "swift" / "Conformance" / "Package.swift").read_text(encoding="utf-8") == (
        "// swift-tools-version: 5.9\n"
    )
    assert (
        target_root / "swift" / "Conformance" / "Sources" / "SwiftConformance" / "main.swift"
    ).read_text(encoding="utf-8") == "print(\"swift conformance\")\n"

def test_kotlin_conformance_harness_shuts_down_okhttp_clients() -> None:
    text = (REPO_ROOT / "examples/kotlin/conformance/Conformance.kt").read_text(
        encoding="utf-8"
    )

    assert "import okhttp3.OkHttpClient" in text
    assert "dispatcher.executorService.shutdown()" in text
    assert "connectionPool.evictAll()" in text
