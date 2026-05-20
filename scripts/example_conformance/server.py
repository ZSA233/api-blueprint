from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen

from scripts import example_validation


@dataclass
class ServerProcess:
    base_url: str
    process: subprocess.Popen[str]
    output_path: Path
    cleanup_dir: Path | None = None

    def stop(self) -> None:
        if self.process.poll() is not None:
            return
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.process.wait(timeout=10)


def reserve_local_addr() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        host, port = sock.getsockname()
    return f"{host}:{port}"


def start_go_server(server_dir: Path) -> ServerProcess:
    addr = reserve_local_addr()
    output_path = server_dir / ".conformance-server.log"
    output = output_path.open("w", encoding="utf-8")
    env = os.environ.copy()
    env["API_BLUEPRINT_EXAMPLE_ADDR"] = addr
    process = subprocess.Popen(
        ["go", "run", "."],
        cwd=server_dir,
        env=env,
        stdout=output,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    server = ServerProcess(base_url=f"http://{addr}", process=process, output_path=output_path)
    try:
        wait_for_go_server(server)
    except Exception:
        server.stop()
        raise
    finally:
        output.close()
    return server


def start_server(server_name: str, blueprint: example_validation.BlueprintExampleWorkspace) -> ServerProcess:
    if server_name == "go":
        return start_go_server(blueprint.golang_server_dir)
    if server_name == "java":
        return start_java_server(blueprint)
    if server_name == "kotlin":
        return start_kotlin_server(blueprint)
    if server_name == "python":
        return start_python_server(blueprint)
    raise ValueError(f"unknown conformance server: {server_name}")


def start_java_server(blueprint: example_validation.BlueprintExampleWorkspace) -> ServerProcess:
    gradle_bin = example_validation.resolve_gradle_bin()
    if gradle_bin is None:
        raise RuntimeError("Gradle is required for Java conformance server")
    addr = reserve_local_addr()
    project_dir = Path(tempfile.mkdtemp(prefix="api-blueprint-java-server-"))
    output_path = project_dir / ".conformance-server.log"
    try:
        source_dir = project_dir / "src/main/java"
        source_dir.mkdir(parents=True)
        server_package = blueprint.java_server_dir / "com"
        if not server_package.is_dir():
            raise RuntimeError(f"Java generated server package is missing: {server_package}")
        shutil.copytree(server_package, source_dir / "com", dirs_exist_ok=True)
        server_app = blueprint.java_conformance_dir / "ServerApp.java"
        if not server_app.is_file():
            raise RuntimeError(f"Java conformance server app is missing: {server_app}")
        server_target = source_dir / "com/example/apiblueprint/conformance/ServerApp.java"
        server_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(server_app, server_target)
        _write_java_server_gradle(project_dir)
        subprocess.run([gradle_bin, "--no-daemon", "installDist"], cwd=project_dir, check=True)
        executable_name = "api-blueprint-java-server.bat" if os.name == "nt" else "api-blueprint-java-server"
        executable = project_dir / "build" / "install" / "api-blueprint-java-server" / "bin" / executable_name
        if not executable.is_file():
            raise RuntimeError(f"Java conformance server executable is missing: {executable}")
        output = output_path.open("w", encoding="utf-8")
        env = os.environ.copy()
        env["API_BLUEPRINT_EXAMPLE_ADDR"] = addr
        process = subprocess.Popen(
            [str(executable)],
            cwd=project_dir,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        server = ServerProcess(base_url=f"http://{addr}", process=process, output_path=output_path, cleanup_dir=project_dir)
        try:
            wait_for_http_server(server, label="java")
        except Exception:
            server.stop()
            raise
        finally:
            output.close()
        return server
    except Exception:
        shutil.rmtree(project_dir, ignore_errors=True)
        raise


def start_kotlin_server(blueprint: example_validation.BlueprintExampleWorkspace) -> ServerProcess:
    gradle_bin = example_validation.resolve_gradle_bin()
    if gradle_bin is None:
        raise RuntimeError("Gradle is required for Kotlin conformance server")
    addr = reserve_local_addr()
    project_dir = Path(tempfile.mkdtemp(prefix="api-blueprint-kotlin-server-"))
    output_path = project_dir / ".conformance-server.log"
    try:
        source_dir = project_dir / "src/main/kotlin"
        server_package = blueprint.kotlin_server_dir / "com"
        if not server_package.is_dir():
            raise RuntimeError(f"Kotlin generated server package is missing: {server_package}")
        shutil.copytree(server_package, source_dir / "com", dirs_exist_ok=True)
        server_app = blueprint.kotlin_conformance_dir / "Server.kt"
        if not server_app.is_file():
            raise RuntimeError(f"Kotlin conformance server app is missing: {server_app}")
        server_target = source_dir / "com/example/apiblueprint/conformance/Server.kt"
        server_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(server_app, server_target)
        _write_kotlin_server_gradle(project_dir)
        subprocess.run([gradle_bin, "--no-daemon", "installDist"], cwd=project_dir, check=True)
        executable_name = "api-blueprint-kotlin-server.bat" if os.name == "nt" else "api-blueprint-kotlin-server"
        executable = project_dir / "build" / "install" / "api-blueprint-kotlin-server" / "bin" / executable_name
        if not executable.is_file():
            raise RuntimeError(f"Kotlin conformance server executable is missing: {executable}")
        output = output_path.open("w", encoding="utf-8")
        env = os.environ.copy()
        env["API_BLUEPRINT_EXAMPLE_ADDR"] = addr
        process = subprocess.Popen(
            [str(executable)],
            cwd=project_dir,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        server = ServerProcess(base_url=f"http://{addr}", process=process, output_path=output_path, cleanup_dir=project_dir)
        try:
            wait_for_http_server(server, label="kotlin")
        except Exception:
            server.stop()
            raise
        finally:
            output.close()
        return server
    except Exception:
        shutil.rmtree(project_dir, ignore_errors=True)
        raise


def start_python_server(blueprint: example_validation.BlueprintExampleWorkspace) -> ServerProcess:
    addr = reserve_local_addr()
    output_path = blueprint.python_dir / ".conformance-server.log"
    output = output_path.open("w", encoding="utf-8")
    env = os.environ.copy()
    env["API_BLUEPRINT_EXAMPLE_ADDR"] = addr
    env["PYTHONPATH"] = str(blueprint.python_dir / "server") + os.pathsep + env.get("PYTHONPATH", "")
    process = subprocess.Popen(
        [sys.executable, "conformance/server_app.py"],
        cwd=blueprint.python_dir,
        env=env,
        stdout=output,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    server = ServerProcess(base_url=f"http://{addr}", process=process, output_path=output_path)
    try:
        wait_for_http_server(server, label="python")
    except Exception:
        server.stop()
        raise
    finally:
        output.close()
    return server


def wait_for_go_server(server: ServerProcess) -> None:
    wait_for_http_server(server, label="go")


def wait_for_http_server(server: ServerProcess, *, label: str) -> None:
    deadline = time.monotonic() + 30
    last_error = ""
    while time.monotonic() < deadline:
        if server.process.poll() is not None:
            raise RuntimeError(
                f"{label} conformance server exited before readiness:\n"
                + server.output_path.read_text(encoding="utf-8", errors="replace")
            )
        try:
            with urlopen(server.base_url + "/api/hello/string", timeout=1) as response:
                if response.status == 200:
                    return
                last_error = f"status {response.status}"
        except Exception as exc:  # noqa: BLE001 - readiness loop records the concrete failure.
            last_error = str(exc)
        time.sleep(0.2)
    raise RuntimeError(
        f"{label} conformance server did not become ready: {last_error}\n"
        + server.output_path.read_text(encoding="utf-8", errors="replace")
    )


def cleanup_server_log(path: Path) -> None:
    if path.name == ".conformance-server.log":
        cleanup_dir = path.parent if path.parent.name.startswith("api-blueprint-") else None
        path.unlink(missing_ok=True)
        if cleanup_dir is not None:
            shutil.rmtree(cleanup_dir, ignore_errors=True)


def _write_java_server_gradle(project_dir: Path) -> None:
    (project_dir / "settings.gradle.kts").write_text(
        'pluginManagement { repositories { gradlePluginPortal(); mavenCentral() } }\n'
        "dependencyResolutionManagement { "
        "repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS); "
        "repositories { mavenCentral() } "
        "}\n"
        'rootProject.name = "api-blueprint-java-server"\n',
        encoding="utf-8",
    )
    (project_dir / "build.gradle.kts").write_text(
        f"""
plugins {{
    java
    application
}}

dependencies {{
    implementation("com.fasterxml.jackson.core:jackson-databind:{example_validation.JACKSON_DATABIND_VERSION}")
    implementation("org.springframework.boot:spring-boot-starter-web:{example_validation.SPRING_BOOT_VERSION}")
    implementation("org.springframework.boot:spring-boot-starter-websocket:{example_validation.SPRING_BOOT_VERSION}")
}}

application {{
    mainClass.set("com.example.apiblueprint.conformance.ServerApp")
}}

java {{
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}}
        """.strip()
        + "\n",
        encoding="utf-8",
    )


def _write_kotlin_server_gradle(project_dir: Path) -> None:
    (project_dir / "settings.gradle.kts").write_text(
        'pluginManagement { repositories { gradlePluginPortal(); mavenCentral() } }\n'
        "dependencyResolutionManagement { "
        "repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS); "
        "repositories { mavenCentral() } "
        "}\n"
        'rootProject.name = "api-blueprint-kotlin-server"\n',
        encoding="utf-8",
    )
    (project_dir / "build.gradle.kts").write_text(
        f"""
plugins {{
    kotlin("jvm") version "{example_validation.KOTLIN_VERSION}"
    kotlin("plugin.serialization") version "{example_validation.KOTLIN_VERSION}"
    application
}}

dependencies {{
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:{example_validation.KOTLINX_COROUTINES_VERSION}")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:{example_validation.KOTLINX_SERIALIZATION_JSON_VERSION}")
    implementation("com.squareup.okio:okio:{example_validation.OKIO_VERSION}")
    implementation("io.ktor:ktor-server-core-jvm:{example_validation.KTOR_VERSION}")
    implementation("io.ktor:ktor-server-netty-jvm:{example_validation.KTOR_VERSION}")
    implementation("io.ktor:ktor-server-websockets-jvm:{example_validation.KTOR_VERSION}")
}}

application {{
    mainClass.set("com.example.apiblueprint.conformance.ServerKt")
}}

java {{
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}}

kotlin {{
    compilerOptions {{
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }}
}}
        """.strip()
        + "\n",
        encoding="utf-8",
    )
