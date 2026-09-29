"""Explicit bounded workloads for the formerly reserved bench commands."""

from __future__ import annotations

import argparse
import json
import sys

from omnismi.probe_runtime import run_probe, run_suite


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def run(argv: list[str], *, command: str) -> int:
    parser = _Parser(prog=f"omnismi bench {command}")
    parser.add_argument(
        "--vendor", required=True, choices=["nvidia", "amd", "alibaba", "cambricon"]
    )
    parser.add_argument(
        "--device", type=int, default=0, help="Runtime-local device index."
    )
    parser.add_argument(
        "--memory-mib", type=int, default=64, help="Total primary device-buffer budget."
    )
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument(
        "--timeout",
        type=float,
        default=90 if command == "suite" else 30,
        help="Whole-command deadline in seconds, maximum 600.",
    )
    try:
        args = vars(parser.parse_args(argv))
        report = (
            run_suite(**args)
            if command == "suite"
            else run_probe(mode="compute", **args)
        )
        print(json.dumps(report, separators=(",", ":"), allow_nan=False))
        return {"PASS": 0, "WARN": 1, "FAIL": 2, "INCONCLUSIVE": 3}[report["status"]]
    except (ValueError, OSError) as exc:
        print(f"omnismi bench {command}: {exc}", file=sys.stderr)
        return 64
