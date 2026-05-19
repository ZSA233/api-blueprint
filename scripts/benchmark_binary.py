from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


TARGETS = ("go", "typescript", "python", "kotlin", "java")
CLIENT_MODULE = "example.com/project/golang/client"
CLIENT_ROUTE_PACKAGE = f"{CLIENT_MODULE}/routes/api/binary"


@dataclass(frozen=True)
class BenchmarkContext:
    repo_root: Path
    count: int
    env: dict[str, str]
    compare_head: bool = False


@dataclass(frozen=True)
class BenchmarkResult:
    target: str
    returncode: int


GO_BENCHMARK_SOURCE = r"""
package tmpbench

import (
	"bytes"
	"testing"

	bin "example.com/project/golang/client/routes/api/binary"
)

func BenchmarkWriteDemoPacket(b *testing.B) {
	packet := &bin.DemoPacket{
		Header: bin.DemoPacketHeader{
			Flags:       0,
			ShortCode:   1,
			SignedDelta: 0,
			ItemCount:   1,
			PayloadLen:  4,
		},
		Body: bin.DemoPacketBody{
			Items: []bin.DemoPacketItem{{
				ID:        1,
				Enabled:   true,
				Value:     1.25,
				LabelLen:  3,
				Label:     []byte("abc"),
			}},
			Payload:  []byte{1, 2, 3, 4},
			Scores:   []float64{1.0, 2.0},
			Checksum: 5,
		},
	}
	var buffer bytes.Buffer
	b.ReportAllocs()
	for index := 0; index < b.N; index++ {
		buffer.Reset()
		if err := packet.WriteBinary(&buffer); err != nil {
			b.Fatal(err)
		}
	}
}
"""


PYTHON_BENCHMARK_SOURCE = r"""
from __future__ import annotations

import io
import sys
import time

from api_blueprint_example_client.api.routes.api.binary.gen_binary import (
    DemoPacket,
    DemoPacketBody,
    DemoPacketHeader,
    DemoPacketItem,
    write_demopacket,
)
from api_blueprint_example_client.api.runtime.binary import BinaryWriter

count = int(sys.argv[1])
packet = DemoPacket(
    header=DemoPacketHeader(flags=0, short_code=1, signed_delta=0, item_count=1, payload_len=4),
    body=DemoPacketBody(
        items=[DemoPacketItem(id=1, enabled=True, value=1.25, label_len=3, label=b"abc")],
        payload=b"\x01\x02\x03\x04",
        scores=[1.0, 2.0],
        checksum=5,
    ),
)
buffer = io.BytesIO()
started = time.perf_counter_ns()
for _ in range(count):
    buffer.seek(0)
    buffer.truncate(0)
    write_demopacket(packet, BinaryWriter(buffer))
elapsed = time.perf_counter_ns() - started
print(f"iterations={count} elapsed_ns={elapsed} ns_per_op={elapsed / count:.1f}")
"""


TYPESCRIPT_BENCHMARK_SOURCE = r"""
declare const process: {
  argv: string[];
  hrtime: { bigint(): bigint };
};

import { DemoPacket, DemoPacketWire } from "./api/routes/api/binary/gen_binary";
import { BinaryWriter } from "./api/runtime/binary/index";

const count = Number.parseInt(process.argv[2] ?? "0", 10);
const packet: DemoPacket = {
  header: { flags: 0, short_code: 1, signed_delta: 0, item_count: 1, payload_len: 4 },
  body: {
    items: [{ id: 1, enabled: true, value: 1.25, label_len: 3, label: new Uint8Array([97, 98, 99]) }],
    payload: new Uint8Array([1, 2, 3, 4]),
    scores: [1.0, 2.0],
    checksum: 5,
  },
};
const started = process.hrtime.bigint();
for (let index = 0; index < count; index += 1) {
  const writer = new BinaryWriter("little");
  DemoPacketWire.write(packet, writer);
  writer.toUint8Array();
}
const elapsed = process.hrtime.bigint() - started;
const elapsedNumber = Number(elapsed);
console.log(`iterations=${count} elapsed_ns=${elapsedNumber} ns_per_op=${(elapsedNumber / count).toFixed(1)}`);
"""


KOTLIN_BENCHMARK_SOURCE = r"""
package tmpbench

import com.example.apiblueprint.api.routes.api.binary.DemoPacket
import com.example.apiblueprint.api.routes.api.binary.DemoPacketBody
import com.example.apiblueprint.api.routes.api.binary.DemoPacketHeader
import com.example.apiblueprint.api.routes.api.binary.DemoPacketItem
import com.example.apiblueprint.api.routes.api.binary.DemoPacketWire
import okio.Buffer

fun main(args: Array<String>) {
    val count = args.firstOrNull()?.toIntOrNull() ?: error("missing count")
    val packet = DemoPacket(
        header = DemoPacketHeader(flags = 0L, shortCode = 1, signedDelta = 0, itemCount = 1, payloadLen = 4L),
        body = DemoPacketBody(
            items = listOf(DemoPacketItem(id = 1L, enabled = true, value = 1.25, labelLen = 3, label = byteArrayOf(97, 98, 99))),
            payload = byteArrayOf(1, 2, 3, 4),
            scores = listOf(1.0, 2.0),
            checksum = 5L,
        ),
    )
    val buffer = Buffer()
    val started = System.nanoTime()
    repeat(count) {
        buffer.clear()
        DemoPacketWire.toBinaryBody(packet).writeTo(buffer)
        buffer.readByteArray()
    }
    val elapsed = System.nanoTime() - started
    println("iterations=$count elapsed_ns=$elapsed ns_per_op=${elapsed.toDouble() / count.toDouble()}")
}
"""


JAVA_BENCHMARK_SOURCE = r"""
package tmpbench;

import com.example.apiblueprint.api.runtime.binary.ApiBinaryBody;
import com.example.apiblueprint.api.routes.api.binary.BinaryTypes;
import java.util.List;

public final class JavaBinaryBenchmark {
    private JavaBinaryBenchmark() {
    }

    public static void main(String[] args) {
        int count = Integer.parseInt(args[0]);
        BinaryTypes.DemoPacket packet = new BinaryTypes.DemoPacket(
            new BinaryTypes.DemoPacketHeader(0L, 1, 0, 1, 4L),
            new BinaryTypes.DemoPacketBody(
                List.of(new BinaryTypes.DemoPacketItem(1L, true, 1.25d, 3, new byte[] {97, 98, 99})),
                new byte[] {1, 2, 3, 4},
                List.of(1.0d, 2.0d),
                5L
            )
        );
        long started = System.nanoTime();
        long total = 0L;
        for (int index = 0; index < count; index++) {
            ApiBinaryBody body = BinaryTypes.DemoPacketWire.toBinaryBody(packet);
            byte[] bytes = body.toBytes();
            BinaryTypes.DemoPacket parsed = BinaryTypes.DemoPacketWire.parse(bytes);
            total += bytes.length + parsed.body().items().size();
        }
        long elapsed = System.nanoTime() - started;
        System.out.println("iterations=" + count + " elapsed_ns=" + elapsed + " ns_per_op=" + ((double) elapsed / (double) count) + " bytes=" + total);
    }
}
"""


JACKSON_JSON_PROPERTY_STUB = r"""
package com.fasterxml.jackson.annotation;

public @interface JsonProperty {
    String value();
}
"""


JACKSON_JSON_IGNORE_PROPERTIES_STUB = r"""
package com.fasterxml.jackson.annotation;

public @interface JsonIgnoreProperties {
    boolean ignoreUnknown() default false;
}
"""


JAVA_API_TYPES_STUB = r"""
package com.example.apiblueprint.api.runtime;

public final class ApiTypes {
    private ApiTypes() {
    }
}
"""


def _run(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, check=False)


def _print_process_output(result: subprocess.CompletedProcess[str]) -> None:
    print(result.stdout + result.stderr, end="")


def _missing_tool(target: str, binary: str) -> BenchmarkResult:
    print(f"\n== {target} ==")
    print(f"missing required tool `{binary}` on PATH; install it or select another --target.")
    return BenchmarkResult(target=target, returncode=127)


def _require_tool(binary: str) -> bool:
    return shutil.which(binary) is not None


def _copytree(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "node_modules", "build"))


def _archive_head_client(repo_root: Path, target_dir: Path, env: dict[str, str]) -> int:
    archive = subprocess.run(
        ["git", "archive", "HEAD:examples/golang/client"],
        cwd=repo_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if archive.returncode != 0:
        print(archive.stderr.decode("utf-8", errors="replace"), end="")
        return archive.returncode
    extract = subprocess.run(["tar", "-x", "-C", str(target_dir)], input=archive.stdout, capture_output=True, check=False, env=env)
    if extract.returncode != 0:
        print((extract.stdout + extract.stderr).decode("utf-8", errors="replace"), end="")
        return extract.returncode
    return 0


def _run_go_client(label: str, client_dir: Path, ctx: BenchmarkContext) -> BenchmarkResult:
    with tempfile.TemporaryDirectory(prefix=f"api-blueprint-binary-bench-go-{label}-") as raw_bench_dir:
        bench_dir = Path(raw_bench_dir)
        commands = [
            ["go", "mod", "init", f"tmpbenchgo{label}"],
            ["go", "mod", "edit", "-replace", f"{CLIENT_MODULE}={client_dir}"],
            ["go", "get", CLIENT_ROUTE_PACKAGE],
        ]
        for command in commands:
            result = _run(command, bench_dir, ctx.env)
            if result.returncode != 0:
                print(f"\n== go:{label} ==")
                _print_process_output(result)
                return BenchmarkResult(target="go", returncode=result.returncode)
        (bench_dir / "binary_write_test.go").write_text(textwrap.dedent(GO_BENCHMARK_SOURCE).strip() + "\n", encoding="utf-8")
        result = _run(["go", "test", "-bench=.", "-benchmem", f"-benchtime={ctx.count}x", "-count=1"], bench_dir, ctx.env)
        print(f"\n== go:{label} ==")
        _print_process_output(result)
        return BenchmarkResult(target="go", returncode=result.returncode)


def run_go(ctx: BenchmarkContext) -> BenchmarkResult:
    if not _require_tool("go"):
        return _missing_tool("go", "go")
    current_client = ctx.repo_root / "examples" / "golang" / "client"
    current_result = _run_go_client("current", current_client, ctx)
    if current_result.returncode != 0 or not ctx.compare_head:
        return current_result
    with tempfile.TemporaryDirectory(prefix="api-blueprint-binary-head-") as raw_head_dir:
        head_dir = Path(raw_head_dir)
        archive_code = _archive_head_client(ctx.repo_root, head_dir, ctx.env)
        if archive_code != 0:
            return BenchmarkResult(target="go", returncode=archive_code)
        return _run_go_client("head", head_dir, ctx)


def run_python(ctx: BenchmarkContext) -> BenchmarkResult:
    with tempfile.TemporaryDirectory(prefix="api-blueprint-binary-bench-python-") as raw_bench_dir:
        bench_dir = Path(raw_bench_dir)
        script = bench_dir / "bench_python.py"
        script.write_text(textwrap.dedent(PYTHON_BENCHMARK_SOURCE).strip() + "\n", encoding="utf-8")
        env = ctx.env.copy()
        python_client = ctx.repo_root / "examples" / "python" / "client"
        env["PYTHONPATH"] = f"{python_client}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
        result = _run([sys.executable, str(script), str(ctx.count)], bench_dir, env)
        print("\n== python ==")
        _print_process_output(result)
        return BenchmarkResult(target="python", returncode=result.returncode)


def run_typescript(ctx: BenchmarkContext) -> BenchmarkResult:
    for binary in ("node", "tsc"):
        if not _require_tool(binary):
            return _missing_tool("typescript", binary)
    with tempfile.TemporaryDirectory(prefix="api-blueprint-binary-bench-typescript-") as raw_bench_dir:
        bench_dir = Path(raw_bench_dir)
        _copytree(ctx.repo_root / "examples" / "typescript" / "api", bench_dir / "api")
        (bench_dir / "bench.ts").write_text(textwrap.dedent(TYPESCRIPT_BENCHMARK_SOURCE).strip() + "\n", encoding="utf-8")
        (bench_dir / "tsconfig.json").write_text(
            textwrap.dedent(
                """
                {
                  "compilerOptions": {
                    "target": "ES2022",
                    "module": "CommonJS",
                    "moduleResolution": "Node",
                    "rootDir": ".",
                    "outDir": "build",
                    "strict": true,
                    "skipLibCheck": true,
                    "esModuleInterop": true
                  },
                  "include": ["bench.ts", "api/**/*.ts"]
                }
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        print("\n== typescript ==")
        compile_result = _run(["tsc", "-p", "tsconfig.json"], bench_dir, ctx.env)
        if compile_result.returncode != 0:
            _print_process_output(compile_result)
            return BenchmarkResult(target="typescript", returncode=compile_result.returncode)
        result = _run(["node", "build/bench.js", str(ctx.count)], bench_dir, ctx.env)
        _print_process_output(result)
        return BenchmarkResult(target="typescript", returncode=result.returncode)


def run_kotlin(ctx: BenchmarkContext) -> BenchmarkResult:
    if not _require_tool("gradle"):
        return _missing_tool("kotlin", "gradle")
    with tempfile.TemporaryDirectory(prefix="api-blueprint-binary-bench-kotlin-") as raw_bench_dir:
        bench_dir = Path(raw_bench_dir)
        kotlin_root = ctx.repo_root / "examples" / "kotlin" / "client" / "com" / "example" / "apiblueprint" / "api"
        temp_api_root = bench_dir / "src" / "main" / "kotlin" / "com" / "example" / "apiblueprint" / "api"
        _copytree(kotlin_root / "runtime", temp_api_root / "runtime")
        _copytree(kotlin_root / "routes" / "api", temp_api_root / "routes" / "api")
        bench_source = bench_dir / "src" / "main" / "kotlin" / "tmpbench" / "KotlinBinaryBenchmark.kt"
        bench_source.parent.mkdir(parents=True, exist_ok=True)
        bench_source.write_text(textwrap.dedent(KOTLIN_BENCHMARK_SOURCE).strip() + "\n", encoding="utf-8")
        (bench_dir / "settings.gradle.kts").write_text('rootProject.name = "api-blueprint-kotlin-binary-bench"\n', encoding="utf-8")
        (bench_dir / "build.gradle.kts").write_text(
            textwrap.dedent(
                """
                plugins {
                    kotlin("jvm") version "2.2.21"
                    kotlin("plugin.serialization") version "2.2.21"
                    application
                }

                repositories {
                    mavenCentral()
                }

                dependencies {
                    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")
                    implementation("com.squareup.okio:okio:3.9.1")
                }

                tasks.withType<JavaCompile>().configureEach {
                    sourceCompatibility = "22"
                    targetCompatibility = "22"
                }

                tasks.withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile>().configureEach {
                    compilerOptions.jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_22)
                }

                application {
                    mainClass.set("tmpbench.KotlinBinaryBenchmarkKt")
                }
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        result = _run(["gradle", "--quiet", "run", "--args", str(ctx.count)], bench_dir, ctx.env)
        print("\n== kotlin ==")
        _print_process_output(result)
        return BenchmarkResult(target="kotlin", returncode=result.returncode)


def run_java(ctx: BenchmarkContext) -> BenchmarkResult:
    for binary in ("javac", "java"):
        if not _require_tool(binary):
            return _missing_tool("java", binary)
    with tempfile.TemporaryDirectory(prefix="api-blueprint-binary-bench-java-") as raw_bench_dir:
        bench_dir = Path(raw_bench_dir)
        source_root = bench_dir / "src"
        classes_dir = bench_dir / "classes"
        classes_dir.mkdir()
        runtime_source = ctx.repo_root / "examples" / "java" / "client" / "com" / "example" / "apiblueprint" / "api" / "runtime" / "binary"
        binary_types_source = ctx.repo_root / "examples" / "java" / "client" / "com" / "example" / "apiblueprint" / "api" / "routes" / "api" / "binary" / "BinaryTypes.java"
        _copytree(runtime_source, source_root / "com" / "example" / "apiblueprint" / "api" / "runtime" / "binary")
        runtime_dir = source_root / "com" / "example" / "apiblueprint" / "api" / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "ApiTypes.java").write_text(textwrap.dedent(JAVA_API_TYPES_STUB).strip() + "\n", encoding="utf-8")
        route_binary_dir = source_root / "com" / "example" / "apiblueprint" / "api" / "routes" / "api" / "binary"
        route_binary_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(binary_types_source, route_binary_dir / "BinaryTypes.java")
        annotation_dir = source_root / "com" / "fasterxml" / "jackson" / "annotation"
        annotation_dir.mkdir(parents=True, exist_ok=True)
        (annotation_dir / "JsonProperty.java").write_text(textwrap.dedent(JACKSON_JSON_PROPERTY_STUB).strip() + "\n", encoding="utf-8")
        (annotation_dir / "JsonIgnoreProperties.java").write_text(
            textwrap.dedent(JACKSON_JSON_IGNORE_PROPERTIES_STUB).strip() + "\n",
            encoding="utf-8",
        )
        bench_source = source_root / "tmpbench" / "JavaBinaryBenchmark.java"
        bench_source.parent.mkdir(parents=True, exist_ok=True)
        bench_source.write_text(textwrap.dedent(JAVA_BENCHMARK_SOURCE).strip() + "\n", encoding="utf-8")
        sources = [str(path) for path in source_root.rglob("*.java")]
        print("\n== java ==")
        compile_result = _run(["javac", "-d", str(classes_dir), *sources], bench_dir, ctx.env)
        if compile_result.returncode != 0:
            _print_process_output(compile_result)
            return BenchmarkResult(target="java", returncode=compile_result.returncode)
        result = _run(["java", "-cp", str(classes_dir), "tmpbench.JavaBinaryBenchmark", str(ctx.count)], bench_dir, ctx.env)
        _print_process_output(result)
        return BenchmarkResult(target="java", returncode=result.returncode)


RUNNERS: dict[str, Callable[[BenchmarkContext], BenchmarkResult]] = {
    "go": run_go,
    "typescript": run_typescript,
    "python": run_python,
    "kotlin": run_kotlin,
    "java": run_java,
}


def _selected_targets(target: str) -> tuple[str, ...]:
    return TARGETS if target == "all" else (target,)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run opt-in binary schema benchmarks without writing tracked files.")
    parser.add_argument("--target", choices=(*TARGETS, "all"), default="go", help="benchmark target language")
    parser.add_argument("--count", type=int, default=10_000, help="operation count for each selected target")
    parser.add_argument("--compare-head", action="store_true", help="also benchmark HEAD:examples/golang/client for the Go target")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1], help="repository root")
    args = parser.parse_args(argv)
    if args.count <= 0:
        parser.error("--count must be greater than zero")

    if args.compare_head and args.target not in ("go", "all"):
        parser.error("--compare-head is only valid with --target go or --target all")

    ctx = BenchmarkContext(repo_root=args.repo_root.resolve(), count=args.count, env=os.environ.copy(), compare_head=args.compare_head)
    print("Note: cross-language benchmark numbers are not normalized; compare trends within a target, not absolute values across languages.")
    exit_code = 0
    for target in _selected_targets(args.target):
        result = RUNNERS[target](ctx)
        if result.returncode != 0 and exit_code == 0:
            exit_code = result.returncode
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
