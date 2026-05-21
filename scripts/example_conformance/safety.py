from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ProbeResponse:
    status: int
    body: bytes


def run_probe(base_url: str, scenario_name: str) -> None:
    if scenario_name == "bad-json":
        _probe_bad_json(base_url)
        return
    if scenario_name == "bad-query":
        _probe_bad_query(base_url)
        return
    if scenario_name == "bad-binary":
        _probe_bad_binary(base_url)
        return
    if scenario_name == "malformed-websocket":
        asyncio.run(_probe_malformed_websocket(base_url))
        return
    if scenario_name == "ws-early-close":
        asyncio.run(_probe_websocket_early_close(base_url))
        return
    raise ValueError(f"unknown server safety scenario: {scenario_name}")


def _probe_bad_json(base_url: str) -> None:
    response = _http_request(
        base_url,
        "POST",
        "/api/demo/test_post",
        body=b"{",
        headers={"Content-Type": "application/json"},
    )
    _require_non_5xx("bad-json", response)


def _probe_bad_query(base_url: str) -> None:
    response = _http_request(
        base_url,
        "GET",
        "/api/hello/hello-way?" + urlencode({"arg1": "not-a-valid-hello-way"}),
    )
    _require_non_5xx("bad-query", response)


def _probe_bad_binary(base_url: str) -> None:
    _http_request(
        base_url,
        "POST",
        "/api/binary/packet?" + urlencode({"trace": "bad-binary"}),
        body=b"not-a-valid-packet",
        headers={"Content-Type": "application/octet-stream"},
    )
    response = _http_request(base_url, "GET", "/api/hello/string")
    _require_non_5xx("bad-binary readiness", response)


async def _probe_malformed_websocket(base_url: str) -> None:
    import websockets
    from websockets.exceptions import ConnectionClosed

    uri = _ws_url(base_url, "/api/demo/assistant-session?" + urlencode({"session_id": "safety-malformed"}))
    async with websockets.connect(uri, open_timeout=5, close_timeout=2) as websocket:
        await websocket.send("not-json")
        try:
            await asyncio.wait_for(websocket.recv(), timeout=5)
        except ConnectionClosed:
            return
        except asyncio.TimeoutError as err:
            raise AssertionError("malformed-websocket did not close or send a close frame") from err


async def _probe_websocket_early_close(base_url: str) -> None:
    import websockets

    uri = _ws_url(base_url, "/api/demo/assistant-session?" + urlencode({"session_id": "safety-early-close"}))
    async with websockets.connect(uri, open_timeout=5, close_timeout=2) as websocket:
        await websocket.send(json.dumps({"type": "input", "data": {"text": "hello"}}))
        await asyncio.wait_for(websocket.recv(), timeout=5)
        await websocket.close()
    response = _http_request(base_url, "GET", "/api/hello/string")
    _require_non_5xx("ws-early-close readiness", response)


def _http_request(
    base_url: str,
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> ProbeResponse:
    request = Request(
        _join_url(base_url, path),
        data=body,
        headers=headers or {},
        method=method,
    )
    try:
        with urlopen(request, timeout=5) as response:
            return ProbeResponse(status=response.status, body=response.read())
    except HTTPError as error:
        return ProbeResponse(status=error.code, body=error.read())


def _require_non_5xx(label: str, response: ProbeResponse) -> None:
    if response.status >= 500:
        body = response.body.decode("utf-8", errors="replace")
        raise AssertionError(f"{label} returned HTTP {response.status}: {body}")


def _join_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def _ws_url(base_url: str, path: str) -> str:
    parts = urlsplit(_join_url(base_url, path))
    scheme = "wss" if parts.scheme == "https" else "ws"
    return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))
