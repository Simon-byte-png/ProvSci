from __future__ import annotations

import argparse

from provsci import __version__
from provsci.schema import WHITELIST_TOOLS


STAGES = ("ingest", "extract", "claims", "path", "verify", "gate")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="provsci", description="科学结果数据智能体")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("status", help="打印当前流水线骨架")
    args = parser.parse_args(argv)

    if args.cmd in (None, "status"):
        print("ProvSci 0.1.0 — 骨架已就位，模块尚未实现")
        print("stages:", " → ".join(STAGES))
        print("whitelist tools:", ", ".join(WHITELIST_TOOLS))
        return 0

    parser.error(f"unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
