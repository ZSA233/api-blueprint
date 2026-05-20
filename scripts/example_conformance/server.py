from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen


@dataclass
class ServerProcess:
    base_url: str
    process: subprocess.Popen[str]
    output_path: Path

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


def wait_for_go_server(server: ServerProcess) -> None:
    deadline = time.monotonic() + 30
    last_error = ""
    while time.monotonic() < deadline:
        if server.process.poll() is not None:
            raise RuntimeError(
                "go conformance server exited before readiness:\n"
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
        f"go conformance server did not become ready: {last_error}\n"
        + server.output_path.read_text(encoding="utf-8", errors="replace")
    )


def cleanup_server_log(path: Path) -> None:
    if path.name == ".conformance-server.log":
        path.unlink(missing_ok=True)

