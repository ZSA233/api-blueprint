from __future__ import annotations

import sys

from benchmark_binary import main as benchmark_main


def main() -> int:
    return benchmark_main([*sys.argv[1:], "--target", "go"])


if __name__ == "__main__":
    raise SystemExit(main())
