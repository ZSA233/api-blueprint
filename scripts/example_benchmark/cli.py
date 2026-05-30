from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

from scripts.example_benchmark import binary, protocol
from scripts.example_conformance import runner
from scripts.example_conformance import manifest, scenarios

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run opt-in generated example benchmarks.")
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT), help="Repository root containing examples/")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List available benchmark targets.")

    binary_parser = subparsers.add_parser("binary", help="Run binary schema benchmarks.")
    binary_parser.add_argument("--target", choices=(*binary.TARGETS, "all"), default="go", help="benchmark target language")
    binary_parser.add_argument("--count", type=int, default=10_000, help="operation count for each selected target")
    binary_parser.add_argument(
        "--compare-head",
        action="store_true",
        help="also benchmark HEAD:examples/golang/client for the Go target",
    )

    protocol_parser = subparsers.add_parser("protocol", help="Run generated example HTTP protocol benchmarks.")
    protocol_parser.add_argument("--servers", default="go", help="Comma-separated servers: go,java,kotlin,python, or all.")
    protocol_parser.add_argument(
        "--scenario",
        default="rpc-json,binary",
        help="Comma-separated scenarios. Supported: rpc-json,form,binary,typed-error.",
    )
    protocol_parser.add_argument("--requests", type=int, default=100, help="measured request count per server/scenario")
    protocol_parser.add_argument("--concurrency", type=int, default=10, help="maximum concurrent requests")
    protocol_parser.add_argument("--warmup", type=int, default=5, help="warmup request count before measurement")
    protocol_parser.add_argument("--keep-workspace", action="store_true", help="Keep temporary workspace after the run.")

    sdk_parser = subparsers.add_parser("sdk-smoke", help="Run generated client SDK smoke benchmark paths.")
    sdk_parser.add_argument("--servers", default="go", help="Comma-separated servers: go,java,kotlin,python, or all.")
    sdk_parser.add_argument(
        "--clients",
        default="python",
        help="Comma-separated generated clients: go,typescript,kotlin,flutter,swift,java,python, or all.",
    )
    sdk_parser.add_argument(
        "--scenario",
        default="request-options,binary-response,media",
        help="Comma-separated conformance scenarios for generated client SDK smoke paths.",
    )
    sdk_parser.add_argument("--keep-workspace", action="store_true", help="Keep temporary workspace after the run.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    try:
        if args.command == "list":
            _print_list()
            return 0
        if args.command == "binary":
            binary_args = [
                "--target",
                args.target,
                "--count",
                str(args.count),
                "--repo-root",
                str(repo_root),
            ]
            if args.compare_head:
                binary_args.append("--compare-head")
            return binary.main(binary_args)
        if args.command == "protocol":
            _validate_positive(args.requests, "--requests")
            _validate_positive(args.concurrency, "--concurrency")
            _validate_non_negative(args.warmup, "--warmup")
            servers = manifest.parse_csv_filter(args.servers, set(manifest.server_manifest()), label="conformance server")
            for item in servers:
                manifest.require_enabled_server(item)
            scenario_names = manifest.parse_csv_filter(
                args.scenario,
                set(protocol.BENCHMARK_SCENARIOS),
                label="benchmark scenario",
            )
            results = asyncio.run(
                protocol.run_protocol_benchmark(
                    protocol.ProtocolBenchmarkOptions(
                        repo_root=repo_root,
                        servers=servers,
                        scenario_names=scenario_names,
                        requests=args.requests,
                        concurrency=args.concurrency,
                        warmup=args.warmup,
                        keep_workspace=args.keep_workspace,
                    )
                )
            )
            protocol.print_protocol_results(results)
            return 0
        if args.command == "sdk-smoke":
            server_names = manifest.parse_csv_filter(args.servers, set(manifest.server_manifest()), label="conformance server")
            client_names = manifest.parse_csv_filter(args.clients, set(manifest.client_manifest()), label="conformance client")
            scenario_names = scenarios.scenario_names_from_cli(args.scenario)
            runner.run_conformance(
                repo_root,
                servers=server_names,
                clients=client_names,
                scenario_names=scenario_names,
                keep_workspace=args.keep_workspace,
            )
            return 0
    except (RuntimeError, ValueError, FileNotFoundError, ModuleNotFoundError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    parser.error(f"unknown command: {args.command}")
    return 1


def _print_list() -> None:
    print("binary targets:")
    for target in binary.TARGETS:
        print(f"- {target}")
    print("protocol servers:")
    for server in manifest.server_manifest().values():
        marker = "enabled" if server.enabled else "planned"
        print(f"- {server.name} {marker}")
    print("protocol scenarios:")
    for scenario_name in protocol.BENCHMARK_SCENARIOS:
        conformance_name = protocol.SCENARIO_ALIASES.get(scenario_name, scenario_name)
        scenario = scenarios.scenario_registry()[conformance_name]
        print(f"- {scenario_name} routes={','.join(scenario.route_ids)}")
    print("sdk smoke scenarios:")
    for scenario_name in ("request-options", "binary-response", "media"):
        scenario = scenarios.scenario_registry()[scenario_name]
        print(f"- {scenario_name} routes={','.join(scenario.route_ids)}")


def _validate_positive(value: int, flag: str) -> None:
    if value <= 0:
        raise ValueError(f"{flag} must be greater than zero")


def _validate_non_negative(value: int, flag: str) -> None:
    if value < 0:
        raise ValueError(f"{flag} must be zero or greater")
