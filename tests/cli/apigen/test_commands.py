from __future__ import annotations

from .helpers import *


def test_api_gen_module_does_not_expose_legacy_split_commands() -> None:
    for name in ("gen_golang", "gen_typescript", "gen_kotlin", "gen_grpc", "gen_wails"):
        assert not hasattr(apigen_module, name)

def test_api_gen_help_only_lists_unified_1_0_commands() -> None:
    result = CliRunner().invoke(api_gen, ["--help"])

    assert result.exit_code == 0
    assert "1.0" in result.output
    assert "vNext" not in result.output
    for command in ("generate", "list-targets", "explain-target", "manifest", "diff", "check", "inspect"):
        assert command in result.output
    for legacy in ("gen-golang", "gen-typescript", "gen-kotlin", "gen-grpc", "gen-wails"):
        assert legacy not in result.output
