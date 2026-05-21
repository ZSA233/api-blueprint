from __future__ import annotations

from .helpers import *


def test_flutter_error_lookup_preserves_dynamic_payload_and_unique_error_constants(tmp_path: Path) -> None:
    class CommonErr(Model):
        UNKNOWN = Error(40000, "common unknown")

    class DemoErr(Model):
        UNKNOWN = Error(40001, "demo unknown")

    class Result(Model):
        ok = String(description="ok")

    bp = Blueprint(root="/api", errors=[CommonErr])
    bp.GET("/demo").RSP(Result).ERR(DemoErr.UNKNOWN)

    out_dir = tmp_path / "flutter"
    writer = FlutterWriter(out_dir, package="api_blueprint_example")
    writer.register(bp)
    writer.gen()

    lookup_text = (
        out_dir / "lib" / "src" / "api" / "runtime" / "gen_api_error_lookup.dart"
    ).read_text(encoding="utf-8")

    assert "static const commonErrUnknown = 40000;" in lookup_text
    assert "static const demoErrUnknown = 40001;" in lookup_text
    assert "ApiErrorPayload mergeApiErrorPayload" in lookup_text
    assert "message: payload.message.isNotEmpty ? payload.message : known.message" in lookup_text
