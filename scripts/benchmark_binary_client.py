from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.example_benchmark.binary import main as benchmark_main


def main() -> int:
    return benchmark_main([*sys.argv[1:], "--target", "go"])


if __name__ == "__main__":
    raise SystemExit(main())
