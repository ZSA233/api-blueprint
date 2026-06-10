from __future__ import annotations

import asyncio
import logging
import os
import struct
import sys
import tempfile
import time
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

import httpx

from scripts.example_conformance import manifest, scenarios, server, tools, workspace


T = TypeVar("T")
BENCHMARK_SCENARIOS = ("rpc-json", "form", "binary", "typed-error")
SCENARIO_ALIASES = {
    "rpc-json": "rpc",
    "typed-error": "error",
}


@dataclass(frozen=True)
class ProtocolBenchmarkOptions:
    repo_root: Path
    servers: tuple[str, ...]
    scenario_names: tuple[str, ...]
    requests: int
    concurrency: int
    warmup: int
    keep_workspace: bool


@dataclass(frozen=True)
class ProtocolBenchmarkResult:
    server: str
    scenario: str
    requests: int
    concurrency: int
    warmup: int
    elapsed: float
    requests_per_second: float
    p50: float
    p95: float
    p99: float
    errors: int


async def run_protocol_benchmark(options: ProtocolBenchmarkOptions) -> list[ProtocolBenchmarkResult]:
    for item in options.servers:
        manifest.require_enabled_server(item)
    selected_scenarios = _selected_scenarios(options.scenario_names)
    tools.ensure_tools_for_targets(options.servers, ())
    conf_workspace = _run_quiet(
        "benchmark workspace generation",
        lambda: workspace.prepare_generated_workspace(options.repo_root),
    )
    results: list[ProtocolBenchmarkResult] = []
    httpx_level = logging.getLogger("httpx").level
    httpcore_level = logging.getLogger("httpcore").level
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    try:
        for server_name in options.servers:
            active_server = _run_quiet(
                f"benchmark server setup ({server_name})",
                lambda: server.start_server(server_name, conf_workspace.blueprint),
            )
            try:
                async with httpx.AsyncClient(
                    base_url=active_server.base_url,
                    timeout=30.0,
                    trust_env=False,
                ) as client:
                    for scenario in selected_scenarios:
                        if not scenarios.server_supports_scenario(server_name, scenario):
                            continue
                        results.append(
                            await _benchmark_scenario(
                                client,
                                server_name,
                                _benchmark_name(scenario.name),
                                scenario.name,
                                options,
                            )
                        )
            finally:
                active_server.stop()
                server.cleanup_server_log(active_server.output_path)
        return results
    finally:
        logging.getLogger("httpx").setLevel(httpx_level)
        logging.getLogger("httpcore").setLevel(httpcore_level)
        if options.keep_workspace:
            print(f"benchmark workspace kept: {conf_workspace.root}")
        elif conf_workspace.temporary:
            import shutil

            shutil.rmtree(conf_workspace.root, ignore_errors=True)


def _run_quiet(label: str, func: Callable[[], T]) -> T:
    captured_output = ""
    try:
        with _capture_process_output() as read_output:
            try:
                return func()
            except Exception:
                captured_output = read_output()
                raise
    except Exception as exc:
        if captured_output.strip():
            raise RuntimeError(f"{label} failed:\n{captured_output}") from exc
        raise


@contextmanager
def _capture_process_output() -> Iterator[Callable[[], str]]:
    saved_stdout = sys.stdout
    saved_stderr = sys.stderr
    stdout_fd = os.dup(1)
    stderr_fd = os.dup(2)
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8", errors="replace") as output:
        try:
            sys.stdout = output
            sys.stderr = output
            os.dup2(output.fileno(), 1)
            os.dup2(output.fileno(), 2)

            def read_output() -> str:
                output.flush()
                output.seek(0)
                return output.read()

            yield read_output
        finally:
            output.flush()
            os.dup2(stdout_fd, 1)
            os.dup2(stderr_fd, 2)
            os.close(stdout_fd)
            os.close(stderr_fd)
            sys.stdout = saved_stdout
            sys.stderr = saved_stderr


async def _benchmark_scenario(
    client: httpx.AsyncClient,
    server_name: str,
    display_scenario: str,
    conformance_scenario: str,
    options: ProtocolBenchmarkOptions,
) -> ProtocolBenchmarkResult:
    request = _request_factory(display_scenario)
    for _ in range(options.warmup):
        await _timed_request(client, request)

    semaphore = asyncio.Semaphore(options.concurrency)
    latencies: list[float] = []
    errors = 0
    started = time.perf_counter()

    async def run_one() -> None:
        nonlocal errors
        async with semaphore:
            elapsed, ok = await _timed_request(client, request)
            latencies.append(elapsed)
            if not ok:
                errors += 1

    await asyncio.gather(*(run_one() for _ in range(options.requests)))
    elapsed = time.perf_counter() - started
    p50, p95, p99 = _percentiles(latencies)
    return ProtocolBenchmarkResult(
        server=server_name,
        scenario=display_scenario,
        requests=options.requests,
        concurrency=options.concurrency,
        warmup=options.warmup,
        elapsed=elapsed,
        requests_per_second=options.requests / elapsed if elapsed > 0 else 0.0,
        p50=p50,
        p95=p95,
        p99=p99,
        errors=errors,
    )


async def _timed_request(
    client: httpx.AsyncClient,
    request: Callable[[httpx.AsyncClient], Awaitable[httpx.Response]],
) -> tuple[float, bool]:
    started = time.perf_counter()
    try:
        response = await request(client)
        return time.perf_counter() - started, response.status_code < 500
    except Exception:
        return time.perf_counter() - started, False


def _selected_scenarios(raw_names: tuple[str, ...]) -> tuple[scenarios.Scenario, ...]:
    selected = scenarios.filter_scenarios(tuple(SCENARIO_ALIASES.get(name, name) for name in raw_names))
    supported_conformance_names = set(SCENARIO_ALIASES.values()) | set(BENCHMARK_SCENARIOS)
    unsupported = [scenario.name for scenario in selected if scenario.name not in supported_conformance_names]
    if unsupported:
        raise ValueError(f"unsupported benchmark scenario: {', '.join(unsupported)}")
    return selected


def _benchmark_name(conformance_name: str) -> str:
    for benchmark_name, scenario_name in SCENARIO_ALIASES.items():
        if scenario_name == conformance_name:
            return benchmark_name
    return conformance_name


def _request_factory(scenario: str) -> Callable[[httpx.AsyncClient], Awaitable[httpx.Response]]:
    if scenario == "rpc-json":
        return _request_rpc
    if scenario == "form":
        return _request_form
    if scenario == "binary":
        return _request_binary
    if scenario == "typed-error":
        return _request_error
    raise ValueError(f"unsupported benchmark scenario: {scenario}")


async def _request_rpc(client: httpx.AsyncClient) -> httpx.Response:
    return await client.post("/api/demo/test_post", json={"req1": "benchmark", "req2": 7})


async def _request_form(client: httpx.AsyncClient) -> httpx.Response:
    return await client.post(
        "/api/demo/form-submit",
        data={"title": "benchmark-form", "count": "4", "enabled": "true"},
    )


async def _request_binary(client: httpx.AsyncClient) -> httpx.Response:
    return await client.post(
        "/api/binary/packet",
        params={"trace": "benchmark"},
        content=_packet_bytes(),
        headers={"content-type": "application/octet-stream"},
    )


async def _request_error(client: httpx.AsyncClient) -> httpx.Response:
    return await client.get("/api/demo/error-demo", params={"mode": "ok"})


async def _request_naming(client: httpx.AsyncClient) -> httpx.Response:
    return await client.get("/api/conflict/default", params={"class": "benchmark"})


def _packet_bytes() -> bytes:
    chunks: list[bytes] = [
        b"ABP1",
        struct.pack("<HH", 1, 1),
        struct.pack("<I", 3),
        b"\x00\x00\x00",
        b"\x03\x02\x01",
        b"\x07\x00\x00",
        struct.pack("<HIH", 2, len(b"payload-ok"), 2),
        _packet_item(11, True, 1.25, b"alpha"),
        _packet_item(22, False, 2.5, b"beta"),
        b"payload-ok",
        struct.pack("<ddI", 3.5, 4.5, 12),
    ]
    return b"".join(chunks)


def _packet_item(item_id: int, enabled: bool, value: float, label: bytes) -> bytes:
    return b"".join(
        [
            struct.pack("<I", item_id),
            b"\x01" if enabled else b"\x00",
            struct.pack("<d", value),
            struct.pack("B", len(label)),
            label,
        ]
    )


def _percentiles(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    ordered = sorted(values)
    return (
        _percentile(ordered, 0.50),
        _percentile(ordered, 0.95),
        _percentile(ordered, 0.99),
    )


def _percentile(ordered: list[float], fraction: float) -> float:
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def print_protocol_results(results: list[ProtocolBenchmarkResult]) -> None:
    for result in results:
        print(
            " ".join(
                [
                    f"server={result.server}",
                    f"scenario={result.scenario}",
                    f"requests={result.requests}",
                    f"concurrency={result.concurrency}",
                    f"warmup={result.warmup}",
                    f"elapsed={result.elapsed:.6f}",
                    f"req/s={result.requests_per_second:.2f}",
                    f"p50={result.p50:.6f}",
                    f"p95={result.p95:.6f}",
                    f"p99={result.p99:.6f}",
                    f"errors={result.errors}",
                ]
            )
        )
