from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from scripts.example_conformance import manifest, runner, scenarios

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run generated examples protocol conformance checks.")
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT), help="Repository root containing examples/")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List enabled servers, clients, and scenarios.")

    generate = subparsers.add_parser("generate", help="Generate examples into a temporary workspace.")
    generate.add_argument("--keep-workspace", action="store_true", help="Print and keep the temporary workspace.")

    for name in ("check", "run", "refresh"):
        command = subparsers.add_parser(name, help=f"{name} generated example conformance.")
        command.add_argument("--server", default="go", help="Server target to start. First phase supports `go`.")
        command.add_argument(
            "--clients",
            default="go,typescript,kotlin,flutter",
            help="Comma-separated clients: go,typescript,kotlin,flutter.",
        )
        command.add_argument(
            "--scenario",
            default="",
            help="Comma-separated scenarios. Defaults to every registered scenario.",
        )
        if name != "refresh":
            command.add_argument("--keep-workspace", action="store_true", help="Keep temporary workspace after the run.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    try:
        if args.command == "list":
            _print_list()
            return 0
        if args.command == "generate":
            runner.generate_conformance_workspace(repo_root, keep_workspace=args.keep_workspace)
            return 0

        clients = manifest.parse_csv_filter(args.clients, set(manifest.client_manifest()), label="conformance client")
        scenario_names = scenarios.scenario_names_from_cli(args.scenario)
        if args.command == "run":
            runner.run_conformance(
                repo_root,
                server=args.server,
                clients=clients,
                scenario_names=scenario_names,
                keep_workspace=args.keep_workspace,
            )
            return 0
        if args.command == "check":
            runner.check_conformance(
                repo_root,
                server_name=args.server,
                clients=clients,
                scenario_names=scenario_names,
                keep_workspace=args.keep_workspace,
            )
            return 0
        if args.command == "refresh":
            runner.refresh_and_check(
                repo_root,
                server_name=args.server,
                clients=clients,
                scenario_names=scenario_names,
            )
            return 0
    except (RuntimeError, ValueError, FileNotFoundError, ModuleNotFoundError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    parser.error(f"unknown command: {args.command}")
    return 1


def _print_list() -> None:
    print("servers:")
    for server in manifest.server_manifest().values():
        marker = "enabled" if server.enabled else "planned"
        print(f"- {server.name} {marker} label={server.command_label}")
    print("clients:")
    for client in manifest.client_manifest().values():
        print(
            f"- {client.name} "
            f"rpc={_yn(client.supports_rpc)} "
            f"sse={_yn(client.supports_sse)} "
            f"websocket={_yn(client.supports_websocket)} "
            f"binary={_yn(client.supports_binary)} "
            f"form={_yn(client.supports_form)} "
            f"connection={client.connection_policy}"
        )
    print("scenarios:")
    for scenario in scenarios.scenario_registry().values():
        print(f"- {scenario.name} clients={','.join(scenario.clients)} routes={','.join(scenario.route_ids)}")


def _yn(value: bool) -> str:
    return "yes" if value else "no"
