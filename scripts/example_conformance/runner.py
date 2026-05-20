from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts import example_validation
from scripts.example_conformance import manifest, reporter, scenarios, server, tools, workspace


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
            for scenario in client_scenarios:
                reporter.run_sub_stage(
                    f"{client}/{scenario.name}",
                    lambda client=client, scenario=scenario: _run_client(
                        conf_workspace.blueprint,
                        client,
                        active_server.base_url,
                        (scenario,),
                    ),
                )
        reporter.print_summary(
            server=server_name,
            clients=clients,
            scenarios=tuple(scenario.name for scenario in selected_scenarios),
        )
    finally:
        active_server.stop()
        server.cleanup_server_log(active_server.output_path)


def _run_client(
    ws: example_validation.BlueprintExampleWorkspace,
    client: str,
    base_url: str,
    selected_scenarios: tuple[scenarios.Scenario, ...],
) -> None:
    scenario_arg = ",".join(scenario.name for scenario in selected_scenarios)
    if client == "go":
        subprocess.run(["go", "run", ".", base_url, scenario_arg], cwd=ws.golang_dir / "conformance", check=True)
        return
    if client == "typescript":
        _run_typescript(ws.typescript_dir, base_url, scenario_arg)
        return
    if client == "kotlin":
        _run_kotlin(ws.kotlin_client_dir, ws.kotlin_conformance_dir, base_url, scenario_arg)
        return
    if client == "flutter":
        env = os.environ.copy()
        env["API_BLUEPRINT_BASE_URL"] = base_url
        env["API_BLUEPRINT_SCENARIOS"] = scenario_arg
        subprocess.run(["dart", "pub", "get"], cwd=ws.flutter_dir, check=True)
        subprocess.run(["dart", "test", "test/conformance_test.dart"], cwd=ws.flutter_dir, env=env, check=True)
        return
    raise ValueError(f"unknown conformance client: {client}")


def _run_typescript(typescript_dir: Path, base_url: str, scenario_arg: str) -> None:
    with tempfile.TemporaryDirectory(prefix="api-blueprint-ts-conformance-") as temp_dir:
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
                temp_dir,
            ],
            cwd=typescript_dir,
            check=True,
        )
        subprocess.run(["node", str(Path(temp_dir) / "conformance.js"), base_url, scenario_arg], cwd=typescript_dir, check=True)


def _run_kotlin(kotlin_dir: Path, conformance_dir: Path, base_url: str, scenario_arg: str) -> None:
    gradle_bin = example_validation.resolve_gradle_bin()
    if gradle_bin is None:
        raise RuntimeError("Gradle is required for Kotlin conformance")
    with tempfile.TemporaryDirectory(prefix="api-blueprint-kotlin-conformance-") as temp_dir:
        project_dir = Path(temp_dir)
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
        subprocess.run([gradle_bin, "--no-daemon", "run", "--args", f"{base_url} {scenario_arg}"], cwd=project_dir, check=True)
