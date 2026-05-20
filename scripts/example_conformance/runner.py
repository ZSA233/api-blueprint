from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Protocol

from scripts import example_validation
from scripts.example_conformance import manifest, reporter, scenarios, server, tools, workspace


class PreparedClientRunner(Protocol):
    def run(self, base_url: str, scenario_arg: str) -> None:
        """Run one already-prepared conformance scenario."""

    def close(self) -> None:
        """Release temporary files or process resources owned by the runner."""


def run_conformance(
    repo_root: Path,
    *,
    server: str,
    clients: tuple[str, ...],
    scenario_names: tuple[str, ...],
    keep_workspace: bool,
) -> None:
    manifest.require_enabled_server(server)
    available_clients = set(manifest.client_manifest())
    unknown_clients = [client for client in clients if client not in available_clients]
    if unknown_clients:
        raise ValueError(f"unknown conformance client: {', '.join(unknown_clients)}")
    selected_scenarios = scenarios.filter_scenarios(scenario_names)
    tools.ensure_tools_for_targets(server, clients)
    conf_workspace = reporter.run_stage("generate examples", lambda: workspace.prepare_generated_workspace(repo_root))
    try:
        _run_against_workspace(
            conf_workspace,
            server_name=server,
            clients=clients,
            selected_scenarios=selected_scenarios,
        )
        if keep_workspace:
            print(f"conformance workspace kept: {conf_workspace.root}")
        elif conf_workspace.temporary:
            shutil.rmtree(conf_workspace.root, ignore_errors=True)
    except Exception:
        if keep_workspace:
            print(f"conformance workspace kept after failure: {conf_workspace.root}", file=sys.stderr)
        elif conf_workspace.temporary:
            shutil.rmtree(conf_workspace.root, ignore_errors=True)
        raise


def check_conformance(
    repo_root: Path,
    *,
    server_name: str,
    clients: tuple[str, ...],
    scenario_names: tuple[str, ...],
    keep_workspace: bool,
) -> None:
    manifest.require_enabled_server(server_name)
    selected_scenarios = scenarios.filter_scenarios(scenario_names)
    tools.ensure_tools_for_targets(server_name, clients)
    conf_workspace = reporter.run_stage("generate examples", lambda: workspace.prepare_generated_workspace(repo_root))
    try:
        reporter.run_stage("check snapshot drift", lambda: workspace.validate_snapshot(repo_root, conf_workspace))
        reporter.run_stage("compile generated examples", lambda: workspace.compile_workspace(conf_workspace))
        _run_against_workspace(
            conf_workspace,
            server_name=server_name,
            clients=clients,
            selected_scenarios=selected_scenarios,
        )
        if keep_workspace:
            print(f"conformance workspace kept: {conf_workspace.root}")
        elif conf_workspace.temporary:
            shutil.rmtree(conf_workspace.root, ignore_errors=True)
    except Exception:
        if keep_workspace:
            print(f"conformance workspace kept after failure: {conf_workspace.root}", file=sys.stderr)
        elif conf_workspace.temporary:
            shutil.rmtree(conf_workspace.root, ignore_errors=True)
        raise


def generate_conformance_workspace(repo_root: Path, *, keep_workspace: bool) -> None:
    conf_workspace = reporter.run_stage("generate examples", lambda: workspace.prepare_generated_workspace(repo_root))
    if keep_workspace:
        print(conf_workspace.root)
        return
    shutil.rmtree(conf_workspace.root, ignore_errors=True)


def refresh_and_check(
    repo_root: Path,
    *,
    server_name: str,
    clients: tuple[str, ...],
    scenario_names: tuple[str, ...],
) -> None:
    manifest.require_enabled_server(server_name)
    selected_scenarios = scenarios.filter_scenarios(scenario_names)
    tools.ensure_tools_for_targets(server_name, clients)
    conf_workspace = reporter.run_stage("refresh examples", lambda: workspace.refresh_repo_workspace(repo_root))
    reporter.run_stage("compile generated examples", lambda: workspace.compile_workspace(conf_workspace))
    _run_against_workspace(
        conf_workspace,
        server_name=server_name,
        clients=clients,
        selected_scenarios=selected_scenarios,
    )


def _run_against_workspace(
    conf_workspace: workspace.ConformanceWorkspace,
    *,
    server_name: str,
    clients: tuple[str, ...],
    selected_scenarios: tuple[scenarios.Scenario, ...],
) -> None:
    active_server = reporter.run_stage(
        f"server {server_name}",
        lambda: server.start_go_server(conf_workspace.blueprint.golang_server_dir),
        success_detail=lambda active: active.base_url,
    )
    try:
        for client in clients:
            client_scenarios = scenarios.runnable_scenarios_for_client(client, selected_scenarios)
            if not client_scenarios:
                reporter.print_skipped(
                    client,
                    "no runnable scenarios for client",
                )
                continue
            reporter.print_group(client)
            prepared_runner = reporter.run_sub_stage(
                f"{client}/setup",
                lambda client=client: _prepare_client_runner(conf_workspace.blueprint, client),
            )
            try:
                for scenario in client_scenarios:
                    reporter.run_sub_stage(
                        f"{client}/{scenario.name}",
                        lambda scenario=scenario, prepared_runner=prepared_runner: prepared_runner.run(
                            active_server.base_url,
                            scenario.name,
                        ),
                    )
            finally:
                prepared_runner.close()
        reporter.print_summary(
            server=server_name,
            clients=clients,
            scenarios=tuple(scenario.name for scenario in selected_scenarios),
        )
    finally:
        active_server.stop()
        server.cleanup_server_log(active_server.output_path)


def _prepare_client_runner(ws: example_validation.BlueprintExampleWorkspace, client: str) -> PreparedClientRunner:
    if client == "go":
        return _prepare_go_runner(ws.golang_dir / "conformance")
    if client == "typescript":
        return _prepare_typescript_runner(ws.typescript_dir)
    if client == "kotlin":
        return _prepare_kotlin_runner(ws.kotlin_client_dir, ws.kotlin_conformance_dir)
    if client == "flutter":
        return _prepare_flutter_runner(ws.flutter_dir)
    raise ValueError(f"unknown conformance client: {client}")


def _run_client(
    ws: example_validation.BlueprintExampleWorkspace,
    client: str,
    base_url: str,
    selected_scenarios: tuple[scenarios.Scenario, ...],
) -> None:
    scenario_arg = ",".join(scenario.name for scenario in selected_scenarios)
    prepared_runner = _prepare_client_runner(ws, client)
    try:
        prepared_runner.run(base_url, scenario_arg)
    finally:
        prepared_runner.close()


class GoConformanceRunner:
    def __init__(self, conformance_dir: Path, temp_dir: Path, executable: Path) -> None:
        self.conformance_dir = conformance_dir
        self.temp_dir = temp_dir
        self.executable = executable

    def run(self, base_url: str, scenario_arg: str) -> None:
        subprocess.run([str(self.executable), base_url, scenario_arg], cwd=self.conformance_dir, check=True)

    def close(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)


def _prepare_go_runner(conformance_dir: Path) -> GoConformanceRunner:
    temp_dir = Path(tempfile.mkdtemp(prefix="api-blueprint-go-conformance-"))
    executable_name = "api-blueprint-go-conformance.exe" if os.name == "nt" else "api-blueprint-go-conformance"
    executable = temp_dir / executable_name
    try:
        subprocess.run(["go", "build", "-o", str(executable), "."], cwd=conformance_dir, check=True)
        return GoConformanceRunner(conformance_dir, temp_dir, executable)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


class TypeScriptConformanceRunner:
    def __init__(self, typescript_dir: Path, temp_dir: Path) -> None:
        self.typescript_dir = typescript_dir
        self.temp_dir = temp_dir

    @property
    def executable(self) -> Path:
        return self.temp_dir / "conformance.js"

    def run(self, base_url: str, scenario_arg: str) -> None:
        subprocess.run(["node", str(self.executable), base_url, scenario_arg], cwd=self.typescript_dir, check=True)

    def close(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)


def _prepare_typescript_runner(typescript_dir: Path) -> TypeScriptConformanceRunner:
    temp_dir = Path(tempfile.mkdtemp(prefix="api-blueprint-ts-conformance-"))
    try:
        subprocess.run(
            [
                "tsc",
                "-p",
                str(typescript_dir / "tsconfig.json"),
                "--module",
                "commonjs",
                "--moduleResolution",
                "node",
                "--outDir",
                str(temp_dir),
            ],
            cwd=typescript_dir,
            check=True,
        )
        return TypeScriptConformanceRunner(typescript_dir, temp_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def _run_typescript(typescript_dir: Path, base_url: str, scenario_arg: str) -> None:
    typescript_runner = _prepare_typescript_runner(typescript_dir)
    try:
        typescript_runner.run(base_url, scenario_arg)
    finally:
        typescript_runner.close()


class FlutterConformanceRunner:
    def __init__(self, flutter_dir: Path) -> None:
        self.flutter_dir = flutter_dir

    def run(self, base_url: str, scenario_arg: str) -> None:
        env = os.environ.copy()
        env["API_BLUEPRINT_BASE_URL"] = base_url
        env["API_BLUEPRINT_SCENARIOS"] = scenario_arg
        subprocess.run(["dart", "test", "test/conformance_test.dart"], cwd=self.flutter_dir, env=env, check=True)

    def close(self) -> None:
        return None


def _prepare_flutter_runner(flutter_dir: Path) -> FlutterConformanceRunner:
    subprocess.run(["dart", "pub", "get"], cwd=flutter_dir, check=True)
    return FlutterConformanceRunner(flutter_dir)


def _run_kotlin(kotlin_dir: Path, conformance_dir: Path, base_url: str, scenario_arg: str) -> None:
    kotlin_runner = _prepare_kotlin_runner(kotlin_dir, conformance_dir)
    try:
        kotlin_runner.run(base_url, scenario_arg)
    finally:
        kotlin_runner.close()


class KotlinConformanceRunner:
    def __init__(self, project_dir: Path, executable: Path) -> None:
        self.project_dir = project_dir
        self.executable = executable

    def run(self, base_url: str, scenario_arg: str) -> None:
        subprocess.run([str(self.executable), base_url, scenario_arg], cwd=self.project_dir, check=True)

    def close(self) -> None:
        shutil.rmtree(self.project_dir, ignore_errors=True)


def _prepare_kotlin_runner(kotlin_dir: Path, conformance_dir: Path) -> KotlinConformanceRunner:
    gradle_bin = example_validation.resolve_gradle_bin()
    if gradle_bin is None:
        raise RuntimeError("Gradle is required for Kotlin conformance")
    project_dir = Path(tempfile.mkdtemp(prefix="api-blueprint-kotlin-conformance-"))
    try:
        source_dir = project_dir / "src/main/kotlin"
        shutil.copytree(kotlin_dir, source_dir)
        conformance_source = conformance_dir / "Conformance.kt"
        if not conformance_source.is_file():
            raise RuntimeError(f"Kotlin conformance source is missing: {conformance_source}")
        conformance_target = source_dir / "com/example/apiblueprint/conformance/Conformance.kt"
        conformance_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(conformance_source, conformance_target)
        (project_dir / "settings.gradle.kts").write_text(
            'pluginManagement { repositories { gradlePluginPortal(); mavenCentral() } }\n'
            "dependencyResolutionManagement { "
            "repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS); "
            "repositories { mavenCentral() } "
            "}\n"
            'rootProject.name = "api-blueprint-kotlin-conformance"\n',
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
    implementation("com.squareup.okhttp3:okhttp:{example_validation.OKHTTP_VERSION}")
    implementation("com.squareup.okio:okio:{example_validation.OKIO_VERSION}")
}}

application {{
    mainClass.set("com.example.apiblueprint.conformance.ConformanceKt")
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
        subprocess.run([gradle_bin, "--no-daemon", "installDist"], cwd=project_dir, check=True)
        executable_name = "api-blueprint-kotlin-conformance.bat" if os.name == "nt" else "api-blueprint-kotlin-conformance"
        executable = project_dir / "build" / "install" / "api-blueprint-kotlin-conformance" / "bin" / executable_name
        if not executable.is_file():
            raise RuntimeError(f"Kotlin conformance executable is missing: {executable}")
        return KotlinConformanceRunner(project_dir, executable)
    except Exception:
        shutil.rmtree(project_dir, ignore_errors=True)
        raise
